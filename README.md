# 🧬 DNA Report Generator

A secure, open-source web application and CLI tool that processes raw consumer DNA files and generates comprehensive health & ancestry reports.

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey?logo=flask)](https://flask.palletsprojects.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Features

| Category | Details |
|---|---|
| **File Formats** | 23andMe `.txt`, AncestryDNA `.txt`, MyHeritage `.csv`, VCF |
| **APIs** | ClinVar (NCBI), Ensembl VEP, MyVariant.info, gnomAD |
| **Analysis** | Pathogenic variants, Ancestry, Traits, Disease Risk, Carrier Status, Pharmacogenomics, Age-related risk |
| **Export** | Interactive Web Dashboard, Standalone HTML, PDF (ReportLab), JSON |
| **CLI** | Full Click-based CLI for batch processing |

---

## Quickstart

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the web server

```bash
python app.py
# → Open http://localhost:5000
```

### 3. CLI usage

```bash
# Analyze a file
python main.py analyze --file my_dna.txt --name "Jane Smith" --mode fast

# Analyze and export PDF
python main.py analyze --file my_dna.vcf --output-pdf report.pdf

# Use sample data
python main.py sample --name "Demo User"

# List supported formats
python main.py formats
```

---

## Project Structure

```
dna_report_generator/
├── app.py                    # Flask web application
├── main.py                   # Click CLI entry point
├── requirements.txt
│
├── parsers/                  # File format parsers
│   ├── format_detector.py    # Auto-detects file format
│   ├── twentythreeme_parser.py
│   ├── ancestry_parser.py
│   ├── myheritage_parser.py
│   ├── vcf_parser.py
│   └── normalizer.py         # Unified variant schema
│
├── api/                      # External API integrations
│   ├── clinvar.py            # NCBI ClinVar
│   ├── ensembl_vep.py        # Ensembl Variant Effect Predictor
│   ├── myvariant.py          # MyVariant.info (CADD/REVEL)
│   ├── gnomad.py             # gnomAD population frequencies
│   └── aggregator.py         # Orchestrates all API calls
│
├── analysis/                 # Analysis engines
│   ├── categorizer.py        # Variant categorization
│   ├── ancestry.py           # Ancestry composition (AIMs)
│   ├── risk_scorer.py        # Polygenic risk scores
│   ├── pharmacogenomics.py   # Drug-gene interactions
│   └── traits.py             # Physical/sensory traits
│
├── reports/                  # Report generators
│   ├── pdf_generator.py      # ReportLab PDF
│   └── html_generator.py     # Jinja2 HTML
│
├── templates/                # Jinja2 templates
│   ├── index.html            # Landing page
│   └── report.html           # Interactive dashboard
│
└── data/
    └── sample/               # Sample DNA data for demos
```

---

## API Data Sources

All data sources are **free and publicly available** — no commercial licensing required.

| Source | Data | Endpoint |
|---|---|---|
| [NCBI ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) | Clinical significance | E-utilities REST API |
| [Ensembl VEP](https://www.ensembl.org/vep) | Variant effect prediction | REST API |
| [MyVariant.info](https://myvariant.info) | CADD, REVEL scores | REST API |
| [gnomAD](https://gnomad.broadinstitute.org) | Population frequencies | GraphQL API |

---

## Analysis Categories

1. **Pathogenic Variants** — ClinVar-confirmed disease-causing variants
2. **Ancestry Composition** — Continental ancestry from Ancestry-Informative Markers
3. **Physical Traits** — Eye color, hair, lactose tolerance, caffeine metabolism, etc.
4. **Complex Disease Risk** — Polygenic risk scores for T2D, CAD, cancer, and more
5. **Inherited Conditions** — Carrier status for autosomal conditions (BRCA1/2, HBB, etc.)
6. **Pharmacogenomics** — Drug metabolism variants (CYP2C19, CYP2D6, VKORC1, etc.)
7. **Age-Related Risk** — AMD, late-onset conditions

---

## Important Disclaimer

> ⚠️ **This tool is for informational and educational purposes only.** It does not constitute medical advice, diagnosis, or treatment. Always consult a licensed healthcare provider or certified genetic counselor before making health decisions based on genetic information.

---

## License

MIT — see [LICENSE](LICENSE)
