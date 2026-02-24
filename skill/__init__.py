"""AVAROS OVOS skill entrypoint with generic KPI dispatch."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, List

from ovos_workshop.decorators import fallback_handler
from ovos_workshop.skills import FallbackSkill

from skill._handlers import (
    can_answer as _can_answer_impl,
    dispatch_kpi_for_metric,
    handle_anomaly_check as _handle_anomaly_check_impl,
    handle_compare_energy as _handle_compare_energy_impl,
    handle_compare_metric as _handle_compare_metric_impl,
    handle_control_turn_off as _handle_control_turn_off_impl,
    handle_control_turn_on as _handle_control_turn_on_impl,
    handle_greeting as _handle_greeting_impl,
    handle_help as _handle_help_impl,
    handle_help_capabilities_list as _handle_help_capabilities_list_impl,
    handle_intent_failure as _handle_intent_failure_impl,
    handle_metric_query_fallback as _handle_metric_query_fallback_impl,
    handle_status_profile_show as _handle_status_profile_show_impl,
    handle_status_system_show as _handle_status_system_show_impl,
    handle_trend_energy as _handle_trend_energy_impl,
    handle_trend_metric as _handle_trend_metric_impl,
    handle_trend_scrap as _handle_trend_scrap_impl,
    handle_whatif_temperature as _handle_whatif_temperature_impl,
)
from skill._helpers import (
    canonicalize_asset_id as _canonicalize_asset_id_impl,
    extract_intent_name as _extract_intent_name_impl,
    extract_line_assets_from_text as _extract_line_assets_from_text_impl,
    extract_utterance_text as _extract_utterance_text_impl,
    get_intent_binding as _get_intent_binding_impl,
    get_power_state as _get_power_state_impl,
    is_anomaly_query as _is_anomaly_query_impl,
    is_non_mock_profile as _is_non_mock_profile_impl,
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
from skill.adapters.factory import AdapterFactory
from skill.domain.exceptions import AVAROSError
from skill.domain.models import CanonicalMetric
from skill.services.response_builder import ResponseBuilder
from skill.use_cases.query_dispatcher import QueryDispatcher

INTENT_METRIC_MAP: dict[str, CanonicalMetric] = {
    "kpi.energy.per_unit": CanonicalMetric.ENERGY_PER_UNIT,
    "kpi.energy.total": CanonicalMetric.ENERGY_TOTAL,
    "kpi.oee": CanonicalMetric.OEE,
    "kpi.scrap_rate": CanonicalMetric.SCRAP_RATE,
    "kpi.peak_demand": CanonicalMetric.PEAK_DEMAND,
    "kpi.peak_tariff_exposure": CanonicalMetric.PEAK_TARIFF_EXPOSURE,
    "kpi.rework_rate": CanonicalMetric.REWORK_RATE,
    "kpi.material_efficiency": CanonicalMetric.MATERIAL_EFFICIENCY,
    "kpi.recycled_content": CanonicalMetric.RECYCLED_CONTENT,
    "kpi.supplier_lead_time": CanonicalMetric.SUPPLIER_LEAD_TIME,
    "kpi.supplier_defect_rate": CanonicalMetric.SUPPLIER_DEFECT_RATE,
    "kpi.supplier_on_time": CanonicalMetric.SUPPLIER_ON_TIME,
    "kpi.supplier_co2_per_kg": CanonicalMetric.SUPPLIER_CO2_PER_KG,
    "kpi.throughput": CanonicalMetric.THROUGHPUT,
    "kpi.cycle_time": CanonicalMetric.CYCLE_TIME, "kpi.changeover_time": CanonicalMetric.CHANGEOVER_TIME,
    "kpi.co2.per_unit": CanonicalMetric.CO2_PER_UNIT,
    "kpi.co2.total": CanonicalMetric.CO2_TOTAL,
    "kpi.co2.per_batch": CanonicalMetric.CO2_PER_BATCH,
}

NON_KPI_INTENT_MAP: tuple[tuple[str, str], ...] = (
    ("greeting.intent", "handle_greeting"), ("help.intent", "handle_help"),
    ("compare.metric.intent", "handle_compare_metric"), ("compare.energy.intent", "handle_compare_energy"),
    ("trend.metric.intent", "handle_trend_metric"),
    ("trend.scrap.intent", "handle_trend_scrap"), ("trend.energy.intent", "handle_trend_energy"),
    ("anomaly.production.check.intent", "handle_anomaly_check"),
    ("whatif.temperature.intent", "handle_whatif_temperature"),
    ("control.device.turn_on.intent", "handle_control_turn_on"),
    ("control.device.turn_off.intent", "handle_control_turn_off"),
    ("status.system.show.intent", "handle_status_system_show"), ("status.profile.show.intent", "handle_status_profile_show"),
    ("help.capabilities.list.intent", "handle_help_capabilities_list"),
)

class AVAROSSkill(FallbackSkill):
    """Voice-driven manufacturing KPI assistant."""

    _parse_period = _parse_period_impl
    _resolve_metric_from_utterance = _resolve_metric_from_utterance_impl
    _is_non_mock_profile = _is_non_mock_profile_impl
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
    _resolve_asset_id = _resolve_asset_id_impl
    _resolve_compare_assets = _resolve_compare_assets_impl
    _is_anomaly_query = _is_anomaly_query_impl
    _extract_intent_name = _extract_intent_name_impl

    handle_greeting = _handle_greeting_impl
    handle_help = _handle_help_impl
    handle_compare_metric = _handle_compare_metric_impl
    handle_compare_energy = _handle_compare_energy_impl
    handle_trend_metric = _handle_trend_metric_impl
    handle_trend_scrap = _handle_trend_scrap_impl
    handle_trend_energy = _handle_trend_energy_impl
    handle_anomaly_check = _handle_anomaly_check_impl
    handle_whatif_temperature = _handle_whatif_temperature_impl
    handle_control_turn_on = _handle_control_turn_on_impl
    handle_control_turn_off = _handle_control_turn_off_impl
    handle_status_system_show = _handle_status_system_show_impl
    handle_status_profile_show = _handle_status_profile_show_impl
    handle_help_capabilities_list = _handle_help_capabilities_list_impl
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
        self._loaded_profile: str = "mock"
        self._loaded_platform: str = "mock"
        self._is_initialized: bool = False

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
                "SettingsService initialization failed, using MockAdapter: %s",
                exc,
            )

        self.settings_service = settings_service
        self.adapter_factory = AdapterFactory(settings_service=self.settings_service)
        adapter = self.adapter_factory.create()
        self.dispatcher = QueryDispatcher(adapter=adapter)
        try:
            self.dispatcher._run_async(adapter.initialize())
        except Exception as exc:
            self.log.warning("Adapter initialize failed at startup: %s", exc)
        self.response_builder = ResponseBuilder(verbosity="normal")

        self._loaded_profile = self._resolve_active_profile()
        self._loaded_platform = adapter.platform_name.lower()
        self._register_intent_handlers()

        self.bus.on("avaros.profile.activated", self._handle_profile_switch)
        self.bus.on("intent_failure", self._handle_intent_failure)
        self.log.info(
            "AVAROS skill initialized with adapter: %s (profile='%s')",
            type(adapter).__name__,
            self._loaded_profile,
        )
        self._is_initialized = True

    def _register_intent_handlers(self) -> None:
        """Register intent files at runtime using data-driven mappings."""
        intent_service = getattr(self, "intent_service", None)
        if intent_service is not None and getattr(intent_service, "_bus", None) is None:
            bus = getattr(self, "bus", None)
            if bus is not None:
                intent_service.set_bus(bus)

        def _register(intent_file: str, handler) -> None:
            try:
                self.register_intent_file(intent_file, handler)
            except RuntimeError as exc:
                if "bus not set" not in str(exc):
                    raise
                self.log.warning("Intent registration skipped without bus: %s", intent_file)

        for intent_name in INTENT_METRIC_MAP:
            _register(f"{intent_name}.intent", self._handle_generic_kpi)
        for intent_file, handler_name in NON_KPI_INTENT_MAP:
            _register(intent_file, getattr(self, handler_name))

    def _handle_generic_kpi(self, message) -> None:
        """Generic KPI handler that maps intent name to canonical metric."""
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
            return "mock"
        try:
            return self.settings_service.get_active_profile_name()
        except Exception:
            return "mock"

    def _handle_profile_switch(self, message) -> None:
        profile_name = message.data.get("profile", "")
        self.log.info("Profile switch event received: '%s'", profile_name)
        try:
            self._ensure_runtime_services()
            self._reload_adapter(profile_name)
        except Exception as exc:
            self.log.error(
                "Profile switch reload failed: %s — falling back to mock",
                exc,
            )
            self._force_mock_fallback()

    def _reload_adapter(self, profile_name: str) -> None:
        """Reload adapter and rebuild QueryDispatcher for active profile."""
        if self.adapter_factory is None:
            self.log.warning("No adapter factory — cannot reload")
            return

        loop = asyncio.new_event_loop()
        try:
            new_adapter = loop.run_until_complete(
                self.adapter_factory.reload(profile_name),
            )
        finally:
            loop.close()

        self.dispatcher = QueryDispatcher(adapter=new_adapter)
        if self.response_builder is None:
            self.response_builder = ResponseBuilder(verbosity="normal")
        self._loaded_profile = self._resolve_active_profile()
        self._loaded_platform = new_adapter.platform_name.lower()
        self.log.info(
            "Adapter reloaded: %s (profile='%s', platform='%s')",
            type(new_adapter).__name__,
            self._loaded_profile,
            self._loaded_platform,
        )

    def _force_mock_fallback(self) -> None:
        """Force MockAdapter as safe fallback (DEC-005)."""
        from skill.adapters.mock import MockAdapter

        mock = MockAdapter()
        self.dispatcher = QueryDispatcher(adapter=mock)
        if self.response_builder is None:
            self.response_builder = ResponseBuilder(verbosity="normal")
        self._loaded_profile = "mock"
        self._loaded_platform = "mock"
        self.log.info("Forced MockAdapter fallback")

    def _expected_platform_for_profile(self, profile_name: str) -> str:
        if self.settings_service is None:
            return "mock"
        try:
            config = self.settings_service.get_profile(profile_name)
            platform = ((config.platform_type if config is not None else "mock") or "mock").strip().lower()
            return platform or "mock"
        except Exception:
            return "mock"

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
        """Safely execute dispatch action with runtime recovery + error handling."""
        self._ensure_runtime_services()

        if self.dispatcher is None:
            self.log.warning("Dispatcher missing in %s; attempting recovery", handler_name)
            try:
                if self.settings_service is not None:
                    profile = self.settings_service.get_active_profile_name()
                    self._reload_adapter(profile)
                else:
                    self._force_mock_fallback()
            except Exception as exc:
                self.log.warning("Dispatcher recovery failed: %s", exc)

            if self.dispatcher is None:
                self.speak("AVAROS is still initializing. Please try again.")
                return None

        if self.response_builder is None:
            self.log.warning("Response builder missing in %s; recovering", handler_name)
            self.response_builder = ResponseBuilder(verbosity="normal")

        self._check_profile_mismatch()

        try:
            return action()
        except AVAROSError as exc:
            self.log.error("Error in %s: %s", handler_name, exc, exc_info=True)
            self.speak(exc.user_message)
            return None
        except Exception as exc:
            self.log.error("Error in %s: %s", handler_name, exc, exc_info=True)
            self.speak("Sorry, I encountered an error. Please try again.")
            return None

    def stop(self):
        """Cleanup runtime resources when skill is stopped."""
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

def create_skill():
    return AVAROSSkill()
