import sqlite3

DB = "data/app_2.db"

B1 = (
    "No ML-model-building roles. The candidate is an AI/LLM engineer who applies existing LLM and speech APIs and builds "
    "orchestration, retrieval and agents around them. They do not want a job whose daily work is building and training "
    "models. Triggered only when the role itself is about that: the title or most of the main duties are developing, "
    "training, tuning or evaluating ML models themselves (classical ML such as classification, segmentation, feature "
    "engineering, hyperparameter tuning; deep learning training; fine-tuning as the core job; quantization, CUDA, "
    "GAN/diffusion work; model research). A role titled ML Engineer whose real work is building LLM applications, "
    "pipelines or agents without training models is NOT this blocker. GenAI, RAG or prompt engineering appearing as one "
    "requirement next to a core of model development does not cancel it. Model training, fine-tuning or research "
    "mentioned as one item in a list of skills, or in the company description, of a role about building applications is "
    "NOT this blocker: it is an ordinary skill gap and is scored as one."
)

B5 = (
    "Remote only, no relocation. The candidate wants to work from home in their own country and will not relocate, "
    "commute to an office, or travel to work on-site. Triggered only when the posting clearly requires physical presence: "
    "it states on-site, hybrid, in-office or relocation work, requires working on-site at customer or client locations "
    "(embedded, forward deployed, field work), or offers remote work limited to a country or region that does not include "
    "the candidate's location according to the resume (for example remote within the US only). If the text is vague or may "
    "simply be poorly written and the role could still be remote, it is NOT triggered. If the posting offers remote as one "
    "of the allowed options (for example \"in-office, hybrid, or remote flexibility\"), or lists several countries or "
    "offices only as places the company operates, it is NOT triggered. A relocation or commute wish marked as preferred "
    "or desirable is NOT triggered. A role that only names the employer's country, with no wording about residency, "
    "location or work authorization, is NOT triggered; but a requirement to live in, or be legally authorized to work "
    "in, a country that does not include the candidate IS a restriction and triggers. Also NOT triggered by silence about "
    "the work format, a bare city or country in the header, a preferred office, or \"open to candidates in other locations\"."
)

B6 = (
    "No complex work authorization required. Triggered only when the posting explicitly requires a government security "
    "clearance, requires citizenship or residency of a country that does not include the candidate, states that the "
    "candidate must already be authorized to work in a country where the candidate is not located, or makes employer visa "
    "sponsorship the only way in. A remote role open only to residents of a region is a work-format restriction covered by "
    "the remote blocker, not this one, unless the posting also explicitly names citizenship, a work permit or authorization. "
    "NOT triggered by \"visa sponsorship is not available\" in a fully remote role open to the candidate's region, by "
    "standard export-control or compliance boilerplate, or by silence. Do not assume any citizenship or visa for the "
    "candidate beyond what the resume states."
)

UPDATES = {1: B1, 5: B5, 6: B6}

connection = sqlite3.connect(DB)
for blocker_id, text in UPDATES.items():
    connection.execute("update blocker_rules set text = ? where id = ?", (text, blocker_id))
connection.commit()
for row in connection.execute("select id, [order], substr(text, 1, 60) from blocker_rules order by [order]"):
    print(row)
connection.close()