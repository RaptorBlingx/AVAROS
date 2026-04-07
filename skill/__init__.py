"""AVAROS OVOS skill entrypoint with generic KPI dispatch."""
from __future__ import annotations

import asyncio
import os
import re
import sys
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any, Callable, List

# Allow OVOS SkillManager to import this package from a skill directory where the
# module name is not literally "skill" (standalone docker-compose mode).
if __name__ != "skill":
    sys.modules.setdefault("skill", sys.modules[__name__])

from ovos_workshop.decorators import fallback_handler
from ovos_workshop.decorators.killable import AbortEvent
from ovos_workshop.skills import FallbackSkill
from skill._handlers import (
    can_answer as _can_answer_impl,
    handle_intent_failure as _handle_intent_failure_impl,
    handle_metric_query_fallback as _handle_metric_query_fallback_impl,
)
from skill._system_handlers import (
    handle_control_turn_off as _handle_control_turn_off_impl,
    handle_control_turn_on as _handle_control_turn_on_impl,
    handle_greeting as _handle_greeting_impl,
    handle_help as _handle_help_impl,
    handle_help_capabilities_list as _handle_help_capabilities_list_impl,
    handle_list_assets as _handle_list_assets_impl,
    handle_status_profile_show as _handle_status_profile_show_impl,
    handle_status_system_show as _handle_status_system_show_impl,
    handle_whatif_temperature as _handle_whatif_temperature_impl,
)
from skill._metric_handlers import (
    dispatch_kpi_for_metric,
    handle_anomaly_check as _handle_anomaly_check_impl,
    handle_compare_energy as _handle_compare_energy_impl,
    handle_compare_metric as _handle_compare_metric_impl,
    handle_drift_check as _handle_drift_check_impl,
    handle_trend_energy as _handle_trend_energy_impl,
    handle_trend_metric as _handle_trend_metric_impl,
    handle_trend_scrap as _handle_trend_scrap_impl,
)
from skill._helpers import (
    canonicalize_asset_id as _canonicalize_asset_id_impl,
    extract_intent_name as _extract_intent_name_impl,
    extract_line_assets_from_text as _extract_line_assets_from_text_impl,
    extract_utterance_text as _extract_utterance_text_impl,
    get_asset_registry as _get_asset_registry_impl,
    get_intent_binding as _get_intent_binding_impl,
    get_power_state as _get_power_state_impl,
    is_anomaly_query as _is_anomaly_query_impl,
    is_drift_query as _is_drift_query_impl,
    has_configured_profile as _has_configured_profile_impl,
    parse_numeric_amount as _parse_numeric_amount_impl,
    parse_period as _parse_period_impl,
    power_state_key as _power_state_key_impl,
    require_intent_binding as _require_intent_binding_impl,
    resolve_asset_id as _resolve_asset_id_impl,
    resolve_compare_assets as _resolve_compare_assets_impl,
    resolve_metric_from_utterance as _resolve_metric_from_utterance_impl,
    resolve_temperature_amount as _resolve_temperature_amount_impl,
    set_power_state as _set_power_state_impl,
)
from skill._intent_maps import INTENT_METRIC_MAP, NON_KPI_INTENT_MAP
from skill.adapters.factory import AdapterFactory
from skill.clients.prevention import PreventionClient
from skill.clients.prevention_statistical import StatisticalPreventionClient
from skill.domain.exceptions import AVAROSError
from skill.services.alert_monitor import AlertMonitor
from skill.services.response_builder import ResponseBuilder
from skill.use_cases.query_dispatcher import QueryDispatcher

if TYPE_CHECKING:
    from ovos_bus_client.message import Message

class AVAROSSkill(FallbackSkill):
    """Voice-driven manufacturing KPI assistant."""

    _parse_period = _parse_period_impl
    _resolve_metric_from_utterance = _resolve_metric_from_utterance_impl
    _has_configured_profile = _has_configured_profile_impl
    _get_intent_binding = _get_intent_binding_impl
    _require_intent_binding = _require_intent_binding_impl
    _power_state_key = _power_state_key_impl
    _get_power_state = _get_power_state_impl
    _set_power_state = _set_power_state_impl
    _parse_numeric_amount = _parse_numeric_amount_impl
    _resolve_temperature_amount = _resolve_temperature_amount_impl
    _extract_utterance_text = _extract_utterance_text_impl
    _canonicalize_asset_id = _canonicalize_asset_id_impl
    _extract_line_assets_from_text = _extract_line_assets_from_text_impl
    _get_asset_registry = _get_asset_registry_impl
    _resolve_asset_id = _resolve_asset_id_impl
    _resolve_compare_assets = _resolve_compare_assets_impl
    _is_anomaly_query = _is_anomaly_query_impl
    _is_drift_query = _is_drift_query_impl
    _extract_intent_name = _extract_intent_name_impl

    handle_greeting = _handle_greeting_impl
    handle_help = _handle_help_impl
    handle_compare_metric = _handle_compare_metric_impl
    handle_compare_energy = _handle_compare_energy_impl
    handle_trend_metric = _handle_trend_metric_impl
    handle_trend_scrap = _handle_trend_scrap_impl
    handle_trend_energy = _handle_trend_energy_impl
    handle_anomaly_check = _handle_anomaly_check_impl
    handle_drift_check = _handle_drift_check_impl
    handle_whatif_temperature = _handle_whatif_temperature_impl
    handle_control_turn_on = _handle_control_turn_on_impl
    handle_control_turn_off = _handle_control_turn_off_impl
    handle_status_system_show = _handle_status_system_show_impl
    handle_status_profile_show = _handle_status_profile_show_impl
    handle_help_capabilities_list = _handle_help_capabilities_list_impl
    handle_list_assets = _handle_list_assets_impl
    _handle_intent_failure = _handle_intent_failure_impl
    can_answer = _can_answer_impl
    handle_metric_query_fallback = fallback_handler(95)(_handle_metric_query_fallback_impl)

    def __init__(self, *args, **kwargs):
        """Initialize skill with default zero-config runtime attributes."""
        self._dir = str(Path(__file__).parent)
        self.settings_service = None
        self.adapter_factory: AdapterFactory | None = None
        self.dispatcher: QueryDispatcher | None = None
        self.response_builder: ResponseBuilder | None = None
        self._loaded_profile: str = "unconfigured"
        self._loaded_platform: str = "unconfigured"
        self._is_initialized: bool = False
        self._asset_registry_profile: str = ""
        self._asset_registry_cache: list[Any] | None = None
        self._registered_intent_files: set[str] = set()
        self._registered_entity_files: set[str] = set()
        self._bus_event_handlers_registered: bool = False
        self._alert_monitor: AlertMonitor = AlertMonitor()
        self._alert_scheduler_active: bool = False
        self._prevention_mode: str = "unknown"
        self._prevention_mode_reason: str = ""

        super().__init__(*args, **kwargs)

    @property
    def native_langs(self) -> List[str]:
        """Return only locales with on-disk resource folders."""
        locale_dir = Path(self.res_dir) / "locale"
        if not locale_dir.is_dir():
            return [self.lang]
        available = [d.name for d in locale_dir.iterdir() if d.is_dir()]
        return available or [self.lang]

    def initialize(self):
        """Build runtime services and register intent handlers."""
        if self._is_initialized:
            self.log.info("AVAROS skill already initialized; skipping duplicate initialize()")
            return

        from skill.services.settings import SettingsService

        settings_service = None
        try:
            settings_service = SettingsService()
            settings_service.initialize()
            self.log.info("SettingsService initialized successfully")
        except Exception as exc:
            self.log.warning(
                "SettingsService initialization failed, using UnconfiguredAdapter: %s",
                exc,
            )

        self.settings_service = settings_service
        self.adapter_factory = AdapterFactory(settings_service=self.settings_service)
        adapter = self.adapter_factory.create()
        prevention_client = self._create_prevention_client()
        self.dispatcher = QueryDispatcher(
            adapter=adapter,
            settings_service=self.settings_service,
            prevention_client=prevention_client,
        )
        try:
            self.dispatcher._run_async(adapter.initialize())
        except Exception as exc:
            self.log.warning("Adapter initialize failed at startup: %s", exc)
        self.response_builder = ResponseBuilder(
            verbosity="normal",
            asset_name_resolver=self._resolve_asset_name_for_voice,
        )

        self._loaded_profile = self._resolve_active_profile()
        self._loaded_platform = adapter.platform_name.lower()
        self._register_intent_handlers()

        if not self._bus_event_handlers_registered:
            self.bus.on("avaros.profile.activated", self._handle_profile_switch)
            self.bus.on("avaros.entities.updated", self._handle_asset_entities_updated)
            self.bus.on("intent_failure", self._handle_intent_failure)
            self._bus_event_handlers_registered = True
        self.log.info(
            "AVAROS skill initialized with adapter: %s (profile='%s')",
            type(adapter).__name__,
            self._loaded_profile,
        )
        self._is_initialized = True
        self._start_alert_scheduler()

    def converse(self, message: Message | None = None) -> bool:
        """Decline converse-stage interception so wake-word gating is preserved.

        AVAROS is a fallback skill — it should only handle utterances via the
        registered fallback handler, never by hijacking the converse pipeline
        stage.  Returning ``False`` tells OVOS to continue normal intent
        resolution for every utterance.
        """
        return False

    def _register_intent_handlers(self, *, force: bool = False) -> int:
        """Register intent files at runtime using data-driven mappings.

        Returns:
            Number of freshly-registered intent files.
        """
        intent_service = getattr(self, "intent_service", None)
        if intent_service is not None and getattr(intent_service, "_bus", None) is None:
            bus = getattr(self, "bus", None)
            if bus is not None:
                intent_service.set_bus(bus)

        if force:
            self._registered_intent_files.clear()

        registered_count = 0

        def _register(intent_file: str, handler) -> None:
            nonlocal registered_count
            if not force and intent_file in self._registered_intent_files:
                return
            try:
                self.register_intent_file(intent_file, handler)
            except RuntimeError as exc:
                if "bus not set" not in str(exc):
                    raise
                self.log.warning("Intent registration skipped without bus: %s", intent_file)
                return
            self._registered_intent_files.add(intent_file)
            registered_count += 1

        self._register_entity_files(force=force)
        for intent_name in INTENT_METRIC_MAP:
            _register(f"{intent_name}.intent", self._handle_generic_kpi)
        for intent_file, handler_name in NON_KPI_INTENT_MAP:
            _register(intent_file, getattr(self, handler_name))
        return registered_count

    def _register_entity_files(self, *, force: bool = False) -> None:
        """Register dynamic asset entity files used by intent slots."""
        if force:
            self._registered_entity_files.clear()

        entity_files = (
            "asset.entity",
            "asset_a.entity",
            "asset_b.entity",
            "period.entity",
        )
        for entity_file in entity_files:
            if not force and entity_file in self._registered_entity_files:
                continue
            try:
                self.register_entity_file(entity_file)
            except RuntimeError as exc:
                if "bus not set" not in str(exc):
                    raise
                self.log.warning(
                    "Entity registration skipped without bus: %s",
                    entity_file,
                )
                continue
            self._registered_entity_files.add(entity_file)

    def _handle_generic_kpi(self, message: Message) -> None:
        """Generic KPI handler that maps intent name to canonical metric.

        Includes utterance-based guards to redirect trend/compare/anomaly/drift
        queries that Padatious mis-routed to a KPI intent.
        """
        utterance = self._extract_utterance_text(message).lower()

        if self._is_anomaly_query(utterance):
            self.handle_anomaly_check(message)
            return

        if self._is_drift_query(utterance):
            self.handle_drift_check(message)
            return

        if "trend" in utterance:
            self.handle_trend_metric(message)
            return

        if "compare" in utterance or " vs " in utterance or "versus" in utterance:
            if "energy" in utterance or "power" in utterance:
                self.handle_compare_energy(message)
            else:
                self.handle_compare_metric(message)
            return

        intent_name = self._extract_intent_name(message)
        metric = INTENT_METRIC_MAP.get(intent_name)
        if metric is None:
            self.speak("I don't recognize that metric.")
            return

        dispatch_kpi_for_metric(
            self,
            metric=metric,
            message=message,
            handler_name=f"handle_kpi_{metric.value}",
        )

    def _resolve_active_profile(self) -> str:
        if self.settings_service is None:
            return "unconfigured"
        try:
            return self.settings_service.get_active_profile_name()
        except Exception:
            return "unconfigured"

    def _create_prevention_client(self) -> PreventionClient:
        """Create the best available prevention client (DEC-005).

        Resolution order:
            1. ``PREVENTION_URL`` env var → HttpPreventionClient
            2. SettingsService ``prevention_url`` key → HttpPreventionClient
            3. Fallback → StatisticalPreventionClient (zero-config)
        """
        url = os.environ.get("PREVENTION_URL", "").strip()
        if not url and self.settings_service is not None:
            try:
                url = str(
                    self.settings_service.get_setting("prevention_url", ""),
                ).strip()
            except Exception:
                url = ""

        if not url:
            self._prevention_mode = "fallback"
            self._prevention_mode_reason = "prevention_url_missing"
            self.log.info(
                "PREVENTION_URL not configured — "
                "using StatisticalPreventionClient (zero-config fallback)",
            )
            return StatisticalPreventionClient()

        from skill.clients.prevention_http import HttpPreventionClient

        auth_token = os.environ.get("PREVENTION_AUTH_TOKEN", "").strip()
        if not auth_token and self.settings_service is not None:
            try:
                auth_token = str(
                    self.settings_service.get_setting(
                        "prevention_auth_token", "",
                    ),
                ).strip()
            except Exception:
                auth_token = ""

        self.log.info("Connecting to PREVENTION at %s", url)
        self._prevention_mode = "http"
        self._prevention_mode_reason = "prevention_url_configured"
        return HttpPreventionClient(
            url=url,
            auth_token=auth_token,
        )

    @staticmethod
    def _normalize_asset_lookup_key(value: str) -> str:
        """Normalize free-form identifiers for robust asset comparisons."""
        lowered = value.lower().strip()
        return re.sub(r"[^a-z0-9]", "", lowered)

    def _resolve_asset_name_for_voice(self, asset_id: str) -> str:
        """Resolve display-friendly asset label for speech responses."""
        raw_asset_id = str(asset_id).strip()
        if not raw_asset_id:
            return asset_id

        target = self._normalize_asset_lookup_key(raw_asset_id)
        if not target:
            return raw_asset_id

        settings_service = self.settings_service
        if settings_service is not None:
            try:
                mappings = settings_service.get_asset_mappings()
            except Exception:
                mappings = {}
            if isinstance(mappings, dict):
                for key, mapping in mappings.items():
                    if not isinstance(mapping, dict):
                        continue
                    lookup_values = [str(key)]
                    display_name = str(mapping.get("display_name", "")).strip()
                    if display_name:
                        lookup_values.append(display_name)
                    raw_aliases = mapping.get("aliases", [])
                    if isinstance(raw_aliases, list):
                        lookup_values.extend(
                            str(alias).strip()
                            for alias in raw_aliases
                            if str(alias).strip()
                        )
                    if any(
                        self._normalize_asset_lookup_key(value) == target
                        for value in lookup_values
                    ):
                        return display_name or str(key)

        try:
            assets = self._get_asset_registry()
        except Exception:
            assets = []

        for asset in assets:
            lookup_values = [
                str(getattr(asset, "asset_id", "")),
                str(getattr(asset, "display_name", "")),
            ]
            raw_aliases = getattr(asset, "aliases", [])
            if isinstance(raw_aliases, list):
                lookup_values.extend(
                    str(alias).strip()
                    for alias in raw_aliases
                    if str(alias).strip()
                )
            if any(
                self._normalize_asset_lookup_key(value) == target
                for value in lookup_values
            ):
                display_name = str(getattr(asset, "display_name", "")).strip()
                if display_name:
                    return display_name
                asset_name = str(getattr(asset, "asset_id", "")).strip()
                if asset_name:
                    return asset_name

        return raw_asset_id

    def _handle_profile_switch(self, message: Message) -> None:
        profile_name = message.data.get("profile", "")
        self.log.info("Profile switch event received: '%s'", profile_name)
        try:
            self._ensure_runtime_services()
            self._reload_adapter(profile_name)
        except Exception as exc:
            self.log.error(
                "Profile switch reload failed: %s — falling back to unconfigured",
                exc,
            )
            self._force_unconfigured_fallback()

    def _handle_asset_entities_updated(self, message: Message) -> None:
        """Regenerate and re-register entity files after asset changes.

        The web-ui container mounts skill/ as read-only, so entity files
        written there are silently lost.  This handler regenerates them
        inside the skill container (which owns the files) before asking
        the intent parser to reload.
        """
        profile_name = str(message.data.get("profile", "")).strip()
        self.log.info(
            "Asset entity update event received (profile='%s')",
            profile_name or "unknown",
        )
        self._asset_registry_cache = None
        self._asset_registry_profile = ""
        self._regenerate_entity_files_from_settings(
            profile_name or self._resolve_active_profile(),
        )
        self._register_entity_files(force=True)

    def _regenerate_entity_files_from_settings(self, profile: str) -> None:
        """Write fresh entity files from the current asset registry.

        Calls the file-writing helpers directly to avoid re-emitting the
        bus event (which ``_regenerate_asset_entity_files`` does), preventing
        an infinite notification loop.
        """
        if self.settings_service is None:
            self.log.warning("No SettingsService — cannot regenerate entities")
            return
        try:
            from skill.services.entity_generator import (
                regenerate_asset_entities_for_all_locales,
            )

            assets = self.settings_service._asset_models_for_profile(profile)
            locale_root = self.settings_service._locale_root_path()
            regenerate_asset_entities_for_all_locales(
                assets=assets,
                locale_root=locale_root,
            )
            self.log.info(
                "Regenerated entity files inside skill container (%d assets)",
                len(assets),
            )
        except Exception as exc:
            self.log.warning("Entity file regeneration failed: %s", exc)

    def _reload_adapter(self, profile_name: str) -> None:
        """Reload adapter and rebuild QueryDispatcher for active profile."""
        self._stop_alert_scheduler()

        if self.adapter_factory is None:
            self.log.warning("No adapter factory — cannot reload")
            return

        new_adapter = self._run_adapter_reload(profile_name)

        prevention_client = self._create_prevention_client()
        self.dispatcher = QueryDispatcher(
            adapter=new_adapter,
            settings_service=self.settings_service,
            prevention_client=prevention_client,
        )
        if self.response_builder is None:
            self.response_builder = ResponseBuilder(
                verbosity="normal",
                asset_name_resolver=self._resolve_asset_name_for_voice,
            )
        self._loaded_profile = self._resolve_active_profile()
        self._loaded_platform = new_adapter.platform_name.lower()
        self._asset_registry_cache = None
        self._asset_registry_profile = ""
        self.log.info(
            "Adapter reloaded: %s (profile='%s', platform='%s')",
            type(new_adapter).__name__,
            self._loaded_profile,
            self._loaded_platform,
        )
        self._start_alert_scheduler()

    def _run_adapter_reload(self, profile_name: str) -> Any:
        """Execute adapter reload coroutine using reusable runtime loop."""
        if self.dispatcher is not None:
            return self.dispatcher._run_async(
                self.adapter_factory.reload(profile_name),
            )

        return self._run_with_current_event_loop(
            self.adapter_factory.reload(profile_name),
        )

    def _run_with_current_event_loop(self, coro: Coroutine[Any, Any, Any]) -> Any:
        """Run coroutine in current thread event loop with safe fallback."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            self.log.warning(
                "No current asyncio event loop; creating a fallback loop for reload",
            )
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=30)

        return loop.run_until_complete(coro)

    def _force_unconfigured_fallback(self) -> None:
        """Force UnconfiguredAdapter as safe fallback."""
        from skill.adapters.unconfigured import UnconfiguredAdapter

        fallback = UnconfiguredAdapter()
        prevention_client = StatisticalPreventionClient()
        self._prevention_mode = "fallback"
        self._prevention_mode_reason = "forced_unconfigured_fallback"
        self.dispatcher = QueryDispatcher(
            adapter=fallback,
            settings_service=self.settings_service,
            prevention_client=prevention_client,
        )
        if self.response_builder is None:
            self.response_builder = ResponseBuilder(
                verbosity="normal",
                asset_name_resolver=self._resolve_asset_name_for_voice,
            )
        self._loaded_profile = "unconfigured"
        self._loaded_platform = "unconfigured"
        self.log.info("Forced UnconfiguredAdapter fallback")

    def _expected_platform_for_profile(self, profile_name: str) -> str:
        if self.settings_service is None:
            return "unconfigured"
        try:
            config = self.settings_service.get_profile(profile_name)
            platform = ((config.platform_type if config is not None else "unconfigured") or "unconfigured").strip().lower()
            if platform in {"custom_rest", "reneryo", "mock"}:
                # All configured REST-style profiles are served by GenericRestAdapter.
                return "generic_rest"
            return platform or "unconfigured"
        except Exception:
            return "unconfigured"

    def _ensure_runtime_services(self) -> None:
        """Recreate SettingsService / AdapterFactory if missing at runtime."""
        if self.settings_service is None:
            try:
                from skill.services.settings import SettingsService

                settings_service = SettingsService()
                settings_service.initialize()
                self.settings_service = settings_service
                self.log.info("Recovered SettingsService at runtime")
            except Exception as exc:
                self.log.warning("Runtime SettingsService recovery failed: %s", exc)

        if self.adapter_factory is None and self.settings_service is not None:
            self.adapter_factory = AdapterFactory(
                settings_service=self.settings_service,
            )
            self.log.info("Recovered AdapterFactory at runtime")

    def _check_profile_mismatch(self) -> None:
        """Reload adapter if active profile differs from loaded one."""
        if self.settings_service is None:
            return
        try:
            current = self.settings_service.get_active_profile_name()
            expected_platform = self._expected_platform_for_profile(current)
            if (
                current != self._loaded_profile
                or expected_platform != self._loaded_platform
            ):
                self.log.info(
                    (
                        "Profile/platform mismatch: loaded_profile='%s', "
                        "active_profile='%s', loaded_platform='%s', "
                        "expected_platform='%s'. Reloading."
                    ),
                    self._loaded_profile,
                    current,
                    self._loaded_platform,
                    expected_platform,
                )
                self._reload_adapter(current)
        except Exception as exc:
            self.log.warning("Profile mismatch check failed: %s", exc)

    def _safe_dispatch(self, handler_name: str, action: Callable) -> Any:
        """Safely execute an action with runtime recovery and user-safe errors.

        Args:
            handler_name: Name of the calling handler for structured logs.
            action: Callable that performs the actual dispatch logic.

        Returns:
            Result of ``action`` when successful; otherwise ``None``.
        """
        self._ensure_runtime_services()

        if self.dispatcher is None:
            self.log.warning("Dispatcher missing in %s; attempting recovery", handler_name)
            try:
                if self.settings_service is not None:
                    profile = self.settings_service.get_active_profile_name()
                    self._reload_adapter(profile)
                else:
                    self._force_unconfigured_fallback()
            except Exception as exc:
                self.log.warning("Dispatcher recovery failed: %s", exc)

            if self.dispatcher is None:
                self.speak("AVAROS is still initializing. Please try again.")
                return None

        if self.response_builder is None:
            self.log.warning("Response builder missing in %s; recovering", handler_name)
            self.response_builder = ResponseBuilder(
                verbosity="normal",
                asset_name_resolver=self._resolve_asset_name_for_voice,
            )

        self._check_profile_mismatch()

        try:
            return action()
        except AVAROSError as exc:
            self.log.error("Error in %s: %s", handler_name, exc, exc_info=True)
            self.speak(exc.user_message)
            return None
        except FutureTimeoutError as exc:
            self.log.error("Timeout in %s: %s", handler_name, exc, exc_info=True)
            self.speak(
                "The data platform did not respond in time. "
                "Please check the platform connection and try again.",
            )
            return None
        except AbortEvent:
            self.log.info("%s aborted by new utterance", handler_name)
            return None
        except Exception as exc:
            self.log.error("Error in %s: %s", handler_name, exc, exc_info=True)
            self.speak("Sorry, I encountered an error. Please try again.")
            return None

    # =================================================================
    # Proactive alert scheduler
    # =================================================================

    _ALERT_SCHEDULER_NAME = "avaros_prevention_alert"

    def _start_alert_scheduler(self) -> None:
        """Register the repeating background alert check."""
        from skill.adapters.unconfigured import UnconfiguredAdapter

        if self.dispatcher is None:
            return
        if isinstance(self.dispatcher.adapter, UnconfiguredAdapter):
            self.log.info("Skipping alert scheduler — UnconfiguredAdapter")
            return

        try:
            from skill.domain.alert_models import AlertConfig

            config = AlertConfig()
            if self.settings_service is not None:
                config = self.settings_service.get_alert_config()

            if not config.enabled:
                self.log.info("Proactive alerts disabled in config")
                return

            self.schedule_repeating_event(
                handler=self._run_background_check,
                when=None,
                frequency=config.interval_seconds,
                name=self._ALERT_SCHEDULER_NAME,
            )
            self._alert_scheduler_active = True
            self.log.info(
                "Alert scheduler started (interval=%ds)",
                config.interval_seconds,
            )
        except Exception as exc:
            self.log.warning("Failed to start alert scheduler: %s", exc)

    def _stop_alert_scheduler(self) -> None:
        """Cancel the repeating background alert check."""
        if not self._alert_scheduler_active:
            return
        try:
            self.cancel_scheduled_event(self._ALERT_SCHEDULER_NAME)
        except Exception as exc:
            self.log.warning("Failed to cancel alert scheduler: %s", exc)
        self._alert_scheduler_active = False
        self.log.info("Alert scheduler stopped")

    def _run_background_check(self, message: Message) -> None:
        """Scheduled handler: run checks and speak unsuppressed alerts."""
        from skill.domain.alert_models import AlertConfig, MonitoredPair

        if self.dispatcher is None:
            return

        config = AlertConfig()
        if self.settings_service is not None:
            config = self.settings_service.get_alert_config()

        if not config.enabled:
            self.log.debug("Background check skipped — disabled")
            return

        pairs = self._resolve_monitored_pairs(config)
        if not pairs:
            self.log.debug("Background check skipped — no pairs")
            return

        try:
            events = self._alert_monitor.run_check(
                self.dispatcher, config, pairs,
            )
        except Exception as exc:
            self.log.error("Background check failed: %s", exc)
            return

        voiced = 0
        for event in events:
            if not event.suppressed:
                self.speak(event.message)
                voiced += 1
            self.log.info(
                "Alert [%s] %s/%s severity=%s suppressed=%s",
                event.alert_type,
                event.metric.value,
                event.asset_id,
                event.severity,
                event.suppressed,
            )

        self.log.info(
            "Background check complete: %d events, %d voiced",
            len(events), voiced,
        )

    def _resolve_monitored_pairs(
        self, config: AlertConfig,
    ) -> list[MonitoredPair]:
        """Determine which metric-asset pairs to check.

        If the user configured specific pairs, use those.
        Otherwise, discover from adapter capabilities.
        """
        from skill.domain.alert_models import MonitoredPair

        if config.monitored_pairs:
            return list(config.monitored_pairs)

        if self.dispatcher is None:
            return []

        adapter = self.dispatcher.adapter
        try:
            metrics = adapter.get_supported_metrics()
        except Exception:
            metrics = []
        if not isinstance(metrics, list) or not metrics:
            return []

        try:
            assets = self.dispatcher._run_async(adapter.list_assets())
        except Exception:
            assets = []
        if not assets:
            return []

        asset_ids: list[str] = []
        for asset in assets:
            asset_id = str(getattr(asset, "asset_id", str(asset))).strip()
            if asset_id and asset_id not in asset_ids:
                asset_ids.append(asset_id)

        if not asset_ids:
            return []

        pairs: list[MonitoredPair] = []
        for m in metrics:
            for aid in asset_ids:
                pairs.append(MonitoredPair(metric=m, asset_id=aid))

        return pairs

    def stop(self):
        """Cleanup runtime resources when skill is stopped."""
        self._stop_alert_scheduler()
        try:
            if self.dispatcher is not None:
                shutdown_coro = self.dispatcher.adapter.shutdown()
                try:
                    running_loop = asyncio.get_running_loop()
                except RuntimeError:
                    running_loop = None

                if running_loop and running_loop.is_running():
                    running_loop.create_task(shutdown_coro)
                else:
                    asyncio.run(shutdown_coro)
        except Exception as exc:
            self.log.warning("Adapter shutdown during stop() failed: %s", exc)
        finally:
            self._is_initialized = False
            self._registered_intent_files.clear()
            self._registered_entity_files.clear()
            self._bus_event_handlers_registered = False

def create_skill():
    return AVAROSSkill()
