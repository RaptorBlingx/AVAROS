## WHITE-LABEL SHOP FOR DIGITAL
## INTELLIGENT ASSISTANCE AND HUMAN-AI
## COLLABORATION IN MANUFACTURING


## WASABI 2
## OPEN CALL FOR EXPERIMENTS
Proposal template



## CONTENT
1 Technical Excellence ....................................................................................................................... 1
1.1 Objectives of the experiment ................................................................................................................................. 1
1.2 Experiment overview .......................................................................................................................................... 2
1.3 Scientific and technological excellence ........................................................................................................... 2
1.4 Collaboration with the WASABI team ............................................................................................................... 4
2 Impact ........................................................................................................................................... 5
2.1 Expected impact on the consortium ................................................................................................................ 5
2.2 Dissemination and exploitation strategy ......................................................................................................... 6
3 Implementation ............................................................................................................................. 7
3.1 Work plan ............................................................................................................................................................. 7
3.2 Budget of the experiment .................................................................................................................................. 9
3.3 Consortia presentation .................................................................................................................................... 10


## IDENTIFICATION DATA OF THE EXPERIMENT
Please fill in the table below with the data required.
TITTLE OF THE EXPERIMENT AI-Voice-Assistant-Driven Resource-Optimized Sustainable Manufacturing
## ACRONIM OF THE
## EXPERIMENT
## AVAROS
## SME NAME
ArtiBilim Bilgi ve Egitim Teknolojileri San. Tic. Ltd. Sti.
## SME COUNTRY
## Türkiye
## SME REGION
## Horizon Europe Associated Country

## COMPLIANCE REQUIREMENT
Please fill in the table below with the data required.
## COMPLIANCE REQUIREMENT  YES/NO
Applicant fully complies with GDPR and AI Act
## Yes
Applicant has conducted a self-assessment to identify GDPR and AI Act risks
## Yes
Applicant has measures in place to mitigate identified risks
## Yes





## WASABI 2
## Open Call: Proposal Template
## 1
## 1 TECHNICAL EXCELLENCE
1.1 Objectives of the experiment
Sustainable    performance    in energy intensive and    supply    chain intensive    industries    (plastics,    textile,
automotive...) manufacturing  depends  on  many  small,  daily  decisions,  yet  those  decisions  are  too  often  slow,
fragmented, spreadsheet-driven and mostly dependent to technical staff’s individual knowledge and experience.
Factories must choose suppliers while raw material specifications and lead times keep shifting; hold batch-level
electricity intensity within targets despite peak tariffs and changing machine mixes; reconcile CO₂-eq reports with
real  production  and  procurement  events;  and  anticipate  how  a  material  substitution  or  schedule  change  will
affect scrap, rework, and delivery KPIs. Strengthening supply-chain optimization with a resource-efficiency focus
is therefore a prerequisite for credible, scalable sustainable manufacturing. Artificial intelligence assistance is a
critical  need  to  ensure both  the  manufacturing  efficiency  in  terms  of improving production  quality,  reducing
carbon  footprint  and  so  on,  and  the  performance  of  users,  ie.  workforce,  in  terms  of  enhancing  technical
knowledge  and  skills,  frustration mitigation  to  minimize  risk  and  increase engagement  besides wellbeing  by
intelligent assistance for decision support. This is also a major challenge for our company in the intensive supply
chain environment.
AVAROS aims to address this gap by designing, implementing, and validating an OVOS-based digital assistant that
consolidates distributed supply chain data and supports manufacturing planning optimization by effective supply
chain actor decision making, so engineers and planners can improve energy, material, and carbon performance
through  effective  human–AI  interaction with  a  confident  engagement  with  the  support  of  AI  assistance.  The
assistant aimed  to  be built  on  RENERYO,  ArtiBilim’s existing supply-chain  optimization  backbone  that  already
unifies supplier, process, and batch data; AVAROS adds the conversational layer and optimization workflows while
keeping RENERYO as the trusted KPI and data source.
The experiment is  structured to serve WASABI OC2’s  core aim: move beyond one-off  prototypes  to  portable,
reusable assistants that other SMEs can actually adopt. AVAROS is going to implement the skills for a distributed
supply  chain  environment with  OVOS  and  a  Docker-Compose  deployment  to  lower  integration  cost  and  avoid
lock-in;  prepare  a  shop-ready  package  with  documentation,  installation  checklist,  sample  configuration,  and  a
dockerized  release;  and  publish  it  on  the  WASABI  White-Label  Shop  so  uptake  can be  tracked  and  compared
across  sites.  To  shorten  time-to-value  for  new  adopters,  the  project  also going  to share  anonymized,  sectoral
resource-efficiency analyses that distil what worked, typical parameter ranges, and common pitfalls.
AI  EDIH TÜRKIYE amplifies  replication  and  quality  by  providing  AI  mentorship  during  development,  convening
validation  sessions  with  industrial  stakeholders,  leading  dissemination  and  onboarding  to  its  network,  and
facilitating access to the MEXT Digital Factory testbed  to demonstrate transferability under realistic conditions.
This collaboration ensures that evidence and know-how accompany the code, matching WASABI’s objective of a
repeatable, open, and monitorable pathway from experiment to SME adoption.
The plan is time-bound and verifiable: months M1–M6 deliver the assistant by using ArtıBilim’s plastics/toy site for
needs analysis and as development testbed to secure APIs; months M5–M10 execute multiple-pilot deployment
at  a  supply  chain  driven  factory  to  be  provided  by  AI  EDIH TÜRKIYE and  KPI  measurement  at  the  MEXT  Digital
Factory testbed; months M11–M12 complete packaging and publication on the Shop. By project end, the solution
is expected to achieve a minimum 8% reduction in electricity per unit, a ≥5% material-based efficiency over supply





## WASABI 2
## Open Call: Proposal Template
## 2
chain, and a ≥10%  decrease  in  CO₂-eq  versus  baseline,  with  TRL  advancement  evidenced  through  dual-pilot
validation and post-project onboarding of at least five SMEs.
1.2 Experiment overview
AVAROS targets energy- and supply-chain-intensive discrete manufacturing, starting with plastics/toy production
and designed to transfer to automotive and textile suppliers. The solution is implemented as a Digital Intelligent
Assistant on  top  of RENERYO, ArtıBilim’s  supply-chain  optimisation  backbone  that  already  unifies  supplier,
process,  and  batch  data.  Within  this  backbone,  AVAROS  adds  three  WASABI-stack  components: OVOS for  the
conversational   layer, DocuBoT to   retrieve   and   ground   answers   in   procedures, specifications   and   pilot
documentation,  and PREVENTION to  support  early  detection  of  anomalies  and  risks  in  operations  and  supply
flows. All components are packaged for Docker-Compose so that deployment is portable and repeatable.
The assistant will be embedded in daily planning and operations where fragmented data currently slows action.
Typical use will revolve around supplier and material planning (tracking raw material specifications, lead-times
and   defect/return   trends,   and   surfacing   viable   substitutions),   production   scheduling   and   changeovers
(anticipating electricity-intensity spikes by machine and shift and suggesting schedule tweaks that reduce peak-
tariff exposure), and inventory/scrap control (linking lot quality to rework and scrap so that at-risk materials are
handled   earlier).   Interaction will   be natural-language   (voice/text)   and   oriented   to human–AI   interaction:
engineers and planners ask targeted questions, receive grounded answers with links to the underlying documents
via DocuBoT, and explore “what-if” options while PREVENTION flags unusual patterns that merit attention.
The  experiment will address  four  persistent  challenges:  fragmented  and  latent  data  across  ERP/MES,  sensors,
supplier  declarations  and  LCA  factors;  volatile  operating  conditions  that  make  static  rules  brittle;  supplier
performance drift that propagates to scrap, rework and delivery KPIs; and high cognitive load on staff with critical
knowledge trapped in spreadsheets and individual experience. By closing the loop from signal to action in one
place, AVAROS aims to make decisions faster and more consistent, reduce peak-tariff exposure through schedule
suggestions, and create earlier transparency and benchmarking on suppliers.
Measurable expected improvements at the pilot sites are targeted as: at least 8% reduction in electricity per unit,
≥5% improvement in material efficiency across the supply chain, and ≥10% decrease in CO₂-eq versus baseline.
Beyond these KPIs, the assistant will be packaged as a dockerized OVOS skills with configuration templates and
an  installation  checklist,  published  on  the WASABI  White-Label  Shop together  with  anonymized,  sectoral
resource-efficiency  analyses  that  capture  what  worked  and  typical  parameter  ranges.  This  pairing  of  portable
software and shared know-how is how AVAROS scales from ArtıBilim’s plastics/toy operations to other SMEs, with
AI  EDIH  TÜRKİYE providing   AI   mentorship,   stakeholder   validation   and   dissemination,   and   facilitating
demonstrations at the MEXT Digital Factory to show transferability under realistic conditions.
1.3 Scientific and technological excellence
AVAROS will depart from traditional MES/BI setups by closing the loop from fragmented supply-chain signals to
timely,  guided  action  in  operational  time.  Instead  of  siloed  dashboards  and  spreadsheet  workflows,  the
experiment will deliver a conversational layer on top of RENERYO’s resource-efficiency backbone and will expose
optimization levers (supplier mix, scheduling, material substitution) exactly where planners and engineers work.
The  innovation  will  be  twofold:  (i)  combining  shop-floor  and  supplier  data with  explainable optimization and





## WASABI 2
# Open Call: Proposal Template
## 3
anomaly detection, and (ii) packaging this capability as a portable, repeatable assistant that other SMEs will be
able to adopt without bespoke integration.
Open-source conversational AI will be a first-class design choice. The assistant will be implemented with OVOS
(skill,   intent   handling,   dialogue), DocuBoT (retrieval   grounding   over   procedures,   specifications   and   pilot
documentation), and PREVENTION (early warnings on anomalous patterns in operations and supply flows). These
components will run in a Docker-Compose stack and will be wired to RENERYO via documented REST APIs. Source
code for the AVAROS skill, configuration templates and deployment artefacts will be released under a permissive
license together with a minimal “getting started” dataset and reproducible instructions.
Data portability will be enforced through open exchange formats and interfaces. Operational data and KPIs will
flow as JSON over REST; time-series from machines and sensors will be ingested via MQTT/OPC-UA bridges; batch
and supplier datasets will be imported/exported as CSV/Parquet; model outputs (recommendations, alerts, what-
if scenarios) will be serialized as JSON with versioned schemas. The assistant will not depend on proprietary file
formats;  integration  points  will  be  documented  so  another  SME  will  be  able  to  point  the  assistant  to  its  own
sources with limited adaptation.
Trustworthy-AI practices  will be embedded from day one, drawing on  ArtıBilim’s AIMoDO project experience
under the Horizon  EU  funded AIRISE  programme  (ALTAI  self-assessment,  risk  logging,  model/version  tracking,
reproducible  pipelines).  Human–AI  interaction  will  be  explicit:  the  assistant  will  present  options  with  linked
evidence (DocuBoT sources, KPI traces, assumptions), while users retain control. Robustness will be ensured via
unit/integration tests, canary validation in both pilots, drift checks in PREVENTION and container-level rollback
procedures. Transparency and accountability will be supported by immutable audit logs (queries, data snapshots,
recommendation IDs), model registries and clear escalation playbooks. In view of the EU AI Act, the use case will
be treated as limited-risk decision support for industrial operations, and human oversight, risk management and
performance monitoring will be maintained accordingly.
GDPR  compliance  will  be  ensured  by  design  and  backed  by AIMoDO-derived data-governance  routines  (RDM
checklist, purpose limitation, retention policies), aligned with an ISO/IEC 27001-style ISMS (risk assessment, asset
inventory,  access  control,  logging/monitoring,  backup  and  change  management).  Pilots  will  primarily  process
operational/manufacturing and supplier data; personal data will not be required. If user identifiers appear (e.g.,
login, audit trails), data minimization, role-based access control, pseudonymization where feasible, encryption in
transit  (TLS)  and  at  rest,  least-privilege  keys/secret  management  and  immutable  audit  trails  will  be  applied.  A
lightweight  Data  Management  Plan  will  define  collection,  retention  and  deletion;  processor  arrangements  and
supplier  security  clauses  will  be  documented  (with  preference  for  ISO  27001-certified  hosting  where available);
and where any personal-data processing extends beyond authentication/audit, a DPIA will be performed before
activation.
The assistant will be delivered as a containerized stack orchestrated by Docker-Compose. At the interaction edge,
the OVOS skill (AVAROS) will exchange queries and responses with DocuBoT (for document-grounded answers)
and  PREVENTION  (for anomaly/drift  alerts). Both  services  will  communicate  with  the  RENERYO API façade over
versioned   REST/JSON,   while   RENERYO   will   ingest   operational   data   from   ERP/MES   (ETL/REST),   supplier
declarations  (REST/CSV)  and  IIoT/sensors  (MQTT/OPC-UA).  Data  and  model  artefacts  will  use  open  formats
(JSON/CSV/Parquet). Security controls (TLS, RBAC, audit logging, model/version registry) will be applied across
services within the container boundary, consistent with the governance approach described above. Skills will be
standalone and reusable for other solutions also, beyond RENERYO.





## WASABI 2
# Open Call: Proposal Template
## 4

1.4 Collaboration with the WASABI team
AVAROS will engage the WASABI consortium for component-specific enablement that accelerates conformance
with  the  programme  stack  and  distribution  workflow,  while  keeping  development  and  operations  in-house.
ArtıBilim’s  internal  software  team  (backend,  DevOps  and  data  engineering)  will  lead  build,  integration  and
deployment;  this capability  is  reinforced  by  our  prior  EU-funded  AI  work AIMoDO — AI-assisted  Manufacturing
Model Optimisation under AIRISE, which established our practices in model/version management, reproducible
pipelines and risk logging. In parallel, AI EDIH TÜRKIYE will provide AI mentorship and stakeholder validation to
ensure the assistant is grounded in realistic industrial needs and transferable beyond the pilots.
OVOS + Docker-Compose (core): We will request configuration assistance and initial deployment guidance for
the  official  OVOS  Docker-Compose  project  (image  pinning/versioning  consistent  with  the  stack,  environment
templates, and recommended health checks). We will also seek skill packaging pointers to ensure our dockerized
release, documentation and sample configuration align with Shop requirements.
DocuBoT  (retrieval  grounding): We  will  request setup  and  configuration  guidance to  confirm  the  indexing
pipeline   and   grounding   patterns   (procedures,   specifications,   pilot   documentation),   including   multilingual
support and recommended resource sizing within our stack.
PREVENTION (anomaly/drift): We will request integration guidance focused on data schemas and API endpoints
relevant to energy/material/CO₂-eq KPIs, plus recommended parameters for drift checks and alerting thresholds
in pilot conditions.
WASABI White-Label Shop: For distribution, we will request shop setup support (instance configuration, listing
flow,  and  compliance  items)  so  the  dockerized  OVOS  skill,  installation  checklist  and  sample  configuration  are
published correctly and discoverable.
This  collaboration  model  keeps  the  consortium  focused  on targeted  configuration  and  onboarding  for  OVOS,
DocuBoT,   PREVENTION   and   the   Shop,  while  ArtıBilim’s  in-house   team—supported   by AI  EDIH  TÜRKIYE
mentorship— will execute development, operate the pilots and sustain the solution after publication.





## WASABI 2
# Open Call: Proposal Template
## 5
## 2 IMPACT
2.1 Expected impact on the consortium
AVAROS is designed to deliver three layers of impact at once: technical gains that lift ArtiBilim’s capabilities and
the  maturity  of  the  solution,  economic  gains  that  convert  the KPIs  into  savings  and  operational resilience,  and
scalable  replication  so  other  SMEs  can  adopt  the  results  with  low  risk.  Collaboration  with AI  EDIH  TÜRKIYE
strengthens  each  layer  through  targeted  mentorship  and  market  access  that  benefit  ArtiBilim’s  path  to
deployment; visibility for the Digital Factory within an EU-funded project and the WASABI consortium is a positive
side effect.
Technically, AVAROS will prove that conversational access to resource-efficiency signals (energy, material, CO₂-
eq) shortens the loop from detection to action in real operations. By project end, the pilots are expected to achieve
≥8% reduction in electricity per unit, ≥5% improvement in material efficiency across the supply chain, and ≥10%
decrease  in  CO₂-eq  versus  baseline.  Beyond  the  numbers,  the  assistant  will  reduce  reporting  latency,  surface
supplier and process deviations earlier, and standardize “what-if” exploration. These capabilities persist after the
experiment and compound as data volume grows.
Economically and commercially, the impact concentrates on RENERYO. With AVAROS, RENERYO gains a native DIA
layer  (OVOS  +  DocuBoT  +  PREVENTION)  that  turns analytics  into  timely  guidance  at  the point  of  work.  This  will
increase RENERYO’s competitiveness through faster onboarding, higher day-to-day use, shorter analysis cycles,
and  clearer,  explainable  links  between  actions  and  outcomes. Commercial  value  accrues  in  RENERYO  as  a
stronger product that helps users realize energy, material, and CO₂-eq improvements. The open, dockerized DIA
layer  will  remain  available  via  the  WASABI  Shop. Based  on  benchmarks and  saving  targets, mid-size  plant
adopting the AVAROS for optimization are expected to achieve approximately €15 000 annual savings.
As a manufacturing SME itself, ArtiBilim will also apply AVAROS in its own operations. The plastics/toy site will use
the  assistant  to  optimize  supplier  selection  (recycled-content  and  lead-time  trade-offs),  reduce  peak-tariff
exposure through schedule adjustments, and lower scrap/rework via earlier anomaly detection—translating the
headline  KPIs  into direct cost savings  and more stable delivery performance. This  “build-and-use” approach
tightens  the  feedback  loop  between  product  development  and  shop-floor  reality,  accelerating  learning  and
strengthening ArtiBilim’s reference case for future customers.
The  environmental  dimension  further  reinforces  competitiveness.  By  improving  energy  intensity  and  material
efficiency, AVAROS supports lower embodied emissions at product and batch level and makes supplier impacts
more  transparent.  This  readiness  matters  for  SMEs  exposed  to  evolving  climate  policies,  including CBAM and
buyer-driven  carbon  requirements:  consistent  CO₂-eq  baselines,  supplier  declarations,  and  audit-ready  traces
reduce compliance friction and sustain access to export markets. While CBAM is not the project’s main focus, the
assistant’s  ability  to  organize  data  and  quantify  reductions  provides  a  practical  edge  where  environmental
performance influences commercial outcomes.
Replication and scale are built in so that other SMEs can benefit without vendor lock-in. The WASABI Shop listing
will include the dockerized OVOS skill, an installation checklist, sample configuration, and a minimal “getting-
started”  dataset.  Integration relies  on  open  interfaces  (REST/MQTT/OPC-UA;  JSON/CSV/Parquet),  enabling
adopters  to  point  the assistant at  their  own ERP/MES,  supplier  files,  and  IIoT  feeds  with limited  adaptation.  To





## WASABI 2
# Open Call: Proposal Template
## 6
transfer  know-how—not  just  code—AVAROS  will  also  publish  anonymized  sectoral  resource-efficiency  analyses
that  summarize  what  worked,  typical  parameter  ranges,  and  pitfalls  observed  in  the  pilots.  Together,  these
elements create tangible technical and economic benefits for ArtiBilim and a clear, low-friction pathway for peers
to reproduce impact at their own sites.
While the project’s impact is aimed at ArtiBilim and SME adopters, AI EDIH TÜRKIYE will also benefit in practical
ways: the MEXT Digital Factory will gain a maintained, DIA-integrated demonstration that enriches its showcase
portfolio;  the  mentorship  program  will  gain reusable  training  assets  (scripts,  data  schemas,  checklists)  derived
from the pilots; and outreach activities will have a concrete, sector-relevant example to engage its network and
members.  These  benefits  improve  the  DIH’s  offer  without  altering  the  project’s  focus  on  SME  outcomes,
portability, and open uptake.
2.2 Dissemination and exploitation strategy
Dissemination  & communication: AI EDIH TÜRKIYE will lead targeted outreach to plastics/textile/automotive
suppliers  and  adjacent  sectors,  prioritizing  hands-on  formats  over  generic  promotion.  Core  actions:  (a) MEXT
Digital Factory demo/workshop days showing AVAROS on the digital-twin line; (b) short expert briefs and progress
snapshots on EDIH/MESS channels linking to the WASABI Shop entry; (c) SME clinics (small cohorts) where firms
bring  their  own  data  schemas  to  assess  connector  fit;  and  (d)  one showcase  session at Digital  Factory site  to
present pilot KPIs and transferability. ArtiBilim will provide scripts, KPI summaries, and “how we tuned it” notes;
EDIH will curate audiences and host sessions. KPIs for dissemination: number of engaged SMEs, clinic follow-ups,
Shop downloads will be followed up post project with the targets of ≥5 SME onboarding calls via EDIH, ≥2 external
PoCs within 3 months of listing.”
Exploitation: ArtiBilim will incorporate the DIA features as a native RENERYO capability, improving usability and
differentiation    (conversational    access,    document-grounded    answers,    anomaly    alerts).    The    Shop-listed,
dockerized skills remains freely available to support replication by other SMEs; ArtiBilim’s commercial value arises
from  a stronger  RENERYO  product and  faster  onboarding  for  customers  validated  through  the  pilots.  AI  EDIH
TÜRKIYE  will  keep  the DIA-integrated  demo active  at  MEXT  and  include  AVAROS  in  AI  mentorship  curricula,
channeling interested SMEs toward adoption.
Ownership & IPR:
- Code & packaging: AVAROS OVOS skill and deployment artifacts will be open source (permissive license)
and published via the WASABI White-Label Shop.
- Platform IP: RENERYO (core platform, data models beyond the skills) remains proprietary to ArtiBilim.
- Configurations/connectors: generic  templates  included  in  the  Shop  package;  site-specific  hardening
remains with adopters.
- Data: stakeholders retains ownership of its data; anonymized aggregates/insights will be shared publicly.
- Branding: trademarks remain with their owners; Shop listing follows WASABI branding guidance.
- IPR  plan  timing: A detailed  IPR  &  ownership  plan (covering  code  licensing,  contribution  rules,  data-
sharing boundaries, and branding) will be prepared by the end of Month 2 (M2), in line with the work plan,
and validated with AI EDIH TÜRKIYE to ensure consistency with dissemination and Shop publication.
This  approach  maximizes  uptake  (open,  portable  package),  turns  pilot  learning  into  a  durable  advantage  for
RENERYO users, and keeps governance clear and time-bound for future adopters.





## WASABI 2
# Open Call: Proposal Template
## 7
## 3 IMPLEMENTATION
3.1 Work plan
## Work Package Title: Project Management & Quality
Duration Starting month: M1 Ending month: M12
Objectives: Coordinate, monitor, and ensure quality/compliance; preparations on meetings/events, reports.
Lead partner: ArtiBilim
Task(s) description: * T0.1 Coordination, planning, minutes, risk & issue logs, ethics/compliance tracking.
- T0.2 Prepare & run bi-weekly meetings of ArtiBilim and AI EDIH TÜRKIYE; monitoring meetings (M2/M4/M6/
M8/M10) with live demos; final monitoring event (M12). * T0.3 Financial administration; final Cost Statement.
Partner(s) contributions: AI EDIH TÜRKIYE supports meeting prep, provides dissemination/progress
evidence, and attends reviews.
Expected outcome(s): On-time reviews, documented decisions/actions, audit-ready project records.
Deliverable(s): D0.1 Kick-off pack (M1); D0.2 Monitoring bundles (M2/M4/M6/M8/M10); D0.3 Final event pack
(M12); D0.4 Cost Statement (M12).

## Work Package Title: Requirements, Data Readiness & Architecture
Duration Starting month: M1 Ending month: M2
Objectives: Define scope/use cases; secure data access; set governance (IPR Plan, GDPR-by-design, ISO/IEC
27001–aligned); specify architecture & connectors.
Lead partner: ArtiBilim
Task(s) description: * T1.1 Use-case scoping and KPI baselines. *  T1.2 Data source inventory, access, and
quality checks. *  T1.3 Security & governance setup (roles, audit, retention, DPIA trigger rules). *  T1.4
Technical architecture & connector plan (REST/MQTT/OPC-UA). *   T1.5 Experiment Handbook (EH) v0.1
initialization (scope, baselines, governance). *   T1.6 IPR Plan
Partner(s) contributions: AI EDIH TÜRKIYE validates use cases with stakeholders; advises on pilot data
access constraints and give mentorship on AI scope/use cases and governance.
Expected outcome(s): Clear, approved scope/architecture; ready-to-develop data and governance; EH v0.1
Deliverable(s): D1.1 IPR Plan (M2); D1.2 Requirements & Architecture (M2); D1.3 EH v0.1 (M2).

Work Package Title: DIA Development (OVOS + DocuBoT + PREVENTION; dockerization)
Duration Starting month: M1 Ending month: M6
Objectives: Build the OVOS skill, integrate DocuBoT/PREVENTION, wire RENERYO APIs, and package as
Docker-Compose; validate on ArtiBilim testbed.
Lead partner: ArtiBilim
Task(s) description: * T2.1 OVOS intents/dialogue/what-if flows; RENERYO API bindings. * T2.2 DocuBoT
indexing/grounding pipeline; PREVENTION anomaly/drift hooks. * T2.3 Docker-Compose stack, CI, health
checks, security checklist.  T2.4 Validation on ArtiBilim plastics/toy site (development validation testbed). T2.5
EH updates (alpha/beta notes, schemas, governance).
Partner(s) contributions: AI EDIH TÜRKIYE reviews flows for pilot fit; provides mentoring feedback.





## WASABI 2
# Open Call: Proposal Template
## 8
Expected outcome(s): Alpha (M3) and Beta (M6) builds; testbed-verified stack ready for pilots.
Deliverable(s): D2.1 Alpha package (M3); D2.2 Beta package + security checklist (M6); D2.3 EH v0.2 (M6).

Work Package Title: Integration & Dual Pilots (Parallel at DIH-Designated Factory + MEXT)
Duration Starting month: M5 Ending month: M10
Objectives: Deploy in parallel at a factory designated by AI EDIH TÜRKIYE and at MEXT Digital Factory;
validate KPIs and transferability.
Lead partner: ArtiBilim (Co-lead: AI EDIH TÜRKIYE)
Task(s) description: * T3.1 Pilot Implementation Plan (roles, data flows, success criteria). * T3.2 Parallel
deployment, operator onboarding, and playbooks. * T3.3 KPI baselines (start) and endlines (finish); midline
tuning. * T3.4 Validation workshops with stakeholders.
Partner(s) contributions: AI EDIH TÜRKIYE secures the pilot factory, coordinates MEXT access, convenes
validation workshops.
Expected outcome(s): Demonstrated impact (≥8% electricity/unit; ≥5% material efficiency; ≥10% CO₂-eq);
evidence of transferability.
Deliverable(s): D3.1 Pilot Implementation Plan (M5); D3.2 Validation Report + anonymized KPI dataset (M10).

Work Package Title: Packaging & WASABI Shop Publication
Duration Starting month: M11 Ending month: M12
Objectives: Produce a portable release and replication assets; publish to the WASABI White-Label Shop.
Lead partner: ArtiBilim
Task(s) description: *  T4.1 Dockerized release; installation checklist; sample configuration; minimal
“getting-started” dataset; screenshots/metadata. * T4.2 Shop listing and verification. * T4.3 Experiment
Handbook — finalization (KPI synthesis, exploitation plan, sustainability notes).
Partner(s) contributions: AI EDIH TÜRKIYE reviews replication assets; supports Shop readiness and
dissemination alignment.
Expected outcome(s): Published, reproducible assistant; clear replication pathway for SMEs.
Deliverable(s): 4.1 Shop Listing Live (M11–M12); D4.2 Experiment Handbook — Final (M12); D4.3 Final Release
& Handover (M12).

## Work Package Title: Dissemination, Replication & Mentoring Support
Duration Starting month: M3 Ending month: M12
Objectives: Drive SME uptake through targeted demos, clinics, and EDIH/MESS channels; capture replication
guidance.
Lead partner: AI EDIH TÜRKIYE
Task(s) description: *  T5.1 Dissemination plan; audience curation. *  T5.2 MEXT demo/workshop days; SME
clinics; expert briefs and Shop links via EDIH/MESS channels. *   T5.3 Publish anonymized sectoral resource-
efficiency analyses and replication notes; feed into EH.
Partner(s) contributions: ArtiBilim provides scripts, KPI notes, and replication content; supports demos.
Expected outcome(s): Qualified SME interest; Shop downloads; documented replication know-how.