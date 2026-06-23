"""
CLI Entry Point — DNA Report Generator
Usage: python main.py [COMMAND] [OPTIONS]
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich import box

console = Console()


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


def _run_pipeline(filepath: str, name: str, mode: str, max_variants: int) -> dict:
    """Shared pipeline runner for all CLI commands."""
    # Lazy imports so CLI loads fast
    from parsers import detect_format, normalize_variants
    from parsers.twentythreeme_parser import parse_23andme
    from parsers.ancestry_parser import parse_ancestry
    from parsers.myheritage_parser import parse_myheritage
    from parsers.vcf_parser import parse_vcf
    from api import annotate_variants
    from analysis import (
        categorize_variants, compute_ancestry,
        compute_risk_scores, analyze_pharmacogenomics, analyze_traits,
    )

    parsers_map = {
        "23andme":    parse_23andme,
        "ancestry":   parse_ancestry,
        "myheritage": parse_myheritage,
        "vcf":        parse_vcf,
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        console=console,
        transient=True,
    ) as progress:

        t = progress.add_task("Detecting format...", total=7)

        fmt = detect_format(filepath)
        if fmt == "unknown":
            console.print("[red]✗ Could not detect file format.[/red]")
            sys.exit(1)
        progress.update(t, advance=1, description=f"Format: [cyan]{fmt}[/cyan] — Parsing...")

        parser = parsers_map[fmt]
        raw = parser(filepath)
        progress.update(t, advance=1, description=f"Parsed [bold]{len(raw)}[/bold] raw variants — Normalizing...")

        variants = normalize_variants(raw)
        progress.update(t, advance=1, description=f"Normalized [bold]{len(variants)}[/bold] variants — Annotating APIs...")

        annotated = annotate_variants(variants, mode=mode, max_variants=max_variants)
        progress.update(t, advance=1, description="Categorizing variants...")

        categories  = categorize_variants(annotated)
        progress.update(t, advance=1, description="Computing ancestry & risk scores...")

        ancestry    = compute_ancestry(annotated)
        risk_scores = compute_risk_scores(annotated)
        progress.update(t, advance=1, description="Pharmacogenomics & traits...")

        pgx    = analyze_pharmacogenomics(annotated)
        traits = analyze_traits(annotated)
        progress.update(t, advance=1, description="Done!")

    import uuid
    return {
        "report_id":    str(uuid.uuid4()),
        "name":         name,
        "generated_at": datetime.now().strftime("%B %d, %Y at %H:%M"),
        "summary": {
            "format":              fmt,
            "mode":                mode,
            "total_variants":      len(variants),
            "annotated_variants":  len(annotated),
            "pathogenic_count":    len(categories.get("pathogenic", [])),
        },
        "ancestry":         ancestry,
        "risk_scores":      risk_scores,
        "pharmacogenomics": pgx,
        "traits":           traits,
        "categories":       categories,
    }


# ── CLI Group ────────────────────────────────────────────────────────────────
@click.group()
@click.version_option("1.0.0", prog_name="DNA Report Generator")
def cli():
    """
    🧬 DNA Report Generator — process raw DNA files into health & ancestry reports.

    \b
    Supported formats:  23andMe .txt | AncestryDNA .txt | MyHeritage .csv | VCF
    Data sources:       ClinVar · Ensembl VEP · MyVariant.info · gnomAD
    """
    pass


# ── analyze command ──────────────────────────────────────────────────────────
@cli.command()
@click.option("--file",         "-f", "filepath",    required=True,  help="Path to raw DNA file (.txt, .csv, .vcf)")
@click.option("--name",         "-n",                default="User", help="Your name (for the report header)")
@click.option("--mode",         "-m",                default="fast",
              type=click.Choice(["fast", "full"], case_sensitive=False),
              help="fast = ClinVar+MyVariant | full = all 4 APIs")
@click.option("--max-variants", "-x",                default=500,    help="Max variants to annotate (default: 500)")
@click.option("--output-pdf",                        default=None,   help="Save PDF report to this path")
@click.option("--output-html",                       default=None,   help="Save standalone HTML report to this path")
@click.option("--output-json",                       default=None,   help="Save raw JSON data to this path")
@click.option("--verbose",      "-v", is_flag=True,  default=False,  help="Enable debug logging")
def analyze(filepath, name, mode, max_variants, output_pdf, output_html, output_json, verbose):
    """Analyze a raw DNA file and generate a report."""
    _setup_logging(verbose)

    console.print()
    console.print(Panel.fit(
        "[bold blue]🧬 DNA Report Generator[/bold blue]\n"
        f"[dim]File: {filepath}  |  Mode: {mode}  |  Max variants: {max_variants}[/dim]",
        border_style="blue",
    ))
    console.print()

    # Validate file
    if not Path(filepath).exists():
        console.print(f"[red]✗ File not found: {filepath}[/red]")
        sys.exit(1)

    report_data = _run_pipeline(filepath, name, mode, max_variants)
    _print_summary(report_data)

    # Exports
    if output_pdf:
        from reports import generate_pdf_report
        with console.status(f"[blue]Generating PDF → {output_pdf}[/blue]"):
            generate_pdf_report(report_data, output_pdf)
        console.print(f"[green]✓ PDF saved:[/green] {output_pdf}")

    if output_html:
        from reports import generate_html_report
        with console.status(f"[blue]Generating HTML → {output_html}[/blue]"):
            generate_html_report(report_data, output_html)
        console.print(f"[green]✓ HTML saved:[/green] {output_html}")

    if output_json:
        with open(output_json, "w") as jf:
            json.dump(report_data, jf, indent=2, default=str)
        console.print(f"[green]✓ JSON saved:[/green] {output_json}")

    if not any([output_pdf, output_html, output_json]):
        console.print("\n[dim]Tip: use --output-pdf report.pdf / --output-html report.html / --output-json data.json to export[/dim]")

    console.print()


# ── sample command ───────────────────────────────────────────────────────────
@cli.command()
@click.option("--name",       "-n", default="Demo User",  help="Name for the report")
@click.option("--mode",       "-m", default="fast",
              type=click.Choice(["fast", "full"], case_sensitive=False))
@click.option("--output-pdf",       default=None,  help="Save PDF report to this path")
@click.option("--output-html",      default=None,  help="Save standalone HTML report to this path")
@click.option("--output-json",      default=None,  help="Save raw JSON data to this path")
def sample(name, mode, output_pdf, output_html, output_json):
    """Run analysis on built-in sample DNA data (great for testing)."""
    from data.sample_generator import generate_sample_variants
    from parsers import normalize_variants
    from api import annotate_variants
    from analysis import (
        categorize_variants, compute_ancestry,
        compute_risk_scores, analyze_pharmacogenomics, analyze_traits,
    )
    import uuid

    console.print()
    console.print(Panel.fit(
        "[bold blue]🧬 DNA Report Generator[/bold blue] — [yellow]Sample Mode[/yellow]\n"
        f"[dim]Using built-in demo dataset  |  Mode: {mode}[/dim]",
        border_style="blue",
    ))
    console.print()

    with console.status("[blue]Running sample analysis...[/blue]"):
        raw       = generate_sample_variants()
        variants  = normalize_variants(raw)
        annotated = annotate_variants(variants, mode=mode, max_variants=100)
        cats      = categorize_variants(annotated)
        ancestry  = compute_ancestry(annotated)
        risks     = compute_risk_scores(annotated)
        pgx       = analyze_pharmacogenomics(annotated)
        traits    = analyze_traits(annotated)

    report_data = {
        "report_id":    str(uuid.uuid4()),
        "name":         name,
        "generated_at": datetime.now().strftime("%B %d, %Y at %H:%M"),
        "summary": {
            "format": "sample", "mode": mode,
            "total_variants": len(variants),
            "annotated_variants": len(annotated),
            "pathogenic_count": len(cats.get("pathogenic", [])),
        },
        "ancestry": ancestry, "risk_scores": risks,
        "pharmacogenomics": pgx, "traits": traits, "categories": cats,
    }

    _print_summary(report_data)

    if output_pdf:
        from reports import generate_pdf_report
        generate_pdf_report(report_data, output_pdf)
        console.print(f"[green]✓ PDF saved:[/green] {output_pdf}")
    if output_html:
        from reports import generate_html_report
        generate_html_report(report_data, output_html)
        console.print(f"[green]✓ HTML saved:[/green] {output_html}")
    if output_json:
        with open(output_json, "w") as jf:
            json.dump(report_data, jf, indent=2, default=str)
        console.print(f"[green]✓ JSON saved:[/green] {output_json}")
    console.print()


# ── batch command ─────────────────────────────────────────────────────────────
@cli.command()
@click.option("--input-dir",  "-i", required=True,  help="Directory containing DNA files")
@click.option("--output-dir", "-o", required=True,  help="Directory to write reports into")
@click.option("--mode",       "-m", default="fast",
              type=click.Choice(["fast", "full"], case_sensitive=False))
@click.option("--format",     "-F",
              type=click.Choice(["pdf", "html", "json", "all"], case_sensitive=False),
              default="html", help="Output format for each report")
def batch(input_dir, output_dir, mode, format):
    """Batch-process all DNA files in a directory."""
    from reports import generate_pdf_report, generate_html_report

    input_path  = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    files = list(input_path.glob("*.txt")) + list(input_path.glob("*.csv")) + list(input_path.glob("*.vcf"))
    if not files:
        console.print(f"[yellow]No .txt/.csv/.vcf files found in {input_dir}[/yellow]")
        sys.exit(0)

    console.print(f"\n[bold]Found {len(files)} files to process[/bold]\n")
    success, failed = 0, 0

    for fpath in files:
        console.print(f"[blue]→[/blue] Processing [bold]{fpath.name}[/bold]...")
        try:
            report = _run_pipeline(str(fpath), name=fpath.stem, mode=mode, max_variants=500)
            stem   = output_path / fpath.stem

            if format in ("pdf", "all"):
                generate_pdf_report(report, str(stem.with_suffix(".pdf")))
            if format in ("html", "all"):
                generate_html_report(report, str(stem.with_suffix(".html")))
            if format in ("json", "all"):
                with open(str(stem.with_suffix(".json")), "w") as jf:
                    json.dump(report, jf, indent=2, default=str)

            console.print(f"  [green]✓[/green] {fpath.name} — {report['summary']['total_variants']} variants")
            success += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {fpath.name} — {e}")
            failed += 1

    console.print(f"\n[bold]Batch complete:[/bold] {success} succeeded, {failed} failed\n")


# ── formats command ───────────────────────────────────────────────────────────
@cli.command()
def formats():
    """Show supported DNA file formats and how to export them."""
    table = Table(title="Supported DNA File Formats", box=box.ROUNDED, border_style="blue")
    table.add_column("Provider",    style="bold cyan")
    table.add_column("Extension",   style="yellow")
    table.add_column("Columns")
    table.add_column("How to Export")

    table.add_row(
        "23andMe", ".txt",
        "rsid, chromosome, position, genotype",
        "Browse Raw Data → Download",
    )
    table.add_row(
        "AncestryDNA", ".txt",
        "rsid, chromosome, position, allele1, allele2",
        "Settings → Download DNA Data",
    )
    table.add_row(
        "MyHeritage", ".csv",
        "RSID, CHROMOSOME, POSITION, RESULT",
        "DNA → Manage DNA Kits → Download",
    )
    table.add_row(
        "VCF", ".vcf",
        "CHROM, POS, ID, REF, ALT, ...",
        "Any VCF-compatible tool (GRCh37/38)",
    )

    console.print()
    console.print(table)
    console.print()


# ── serve command ─────────────────────────────────────────────────────────────
@cli.command()
@click.option("--port", "-p", default=5000, help="Port to run on (default: 5000)")
@click.option("--debug", "-d", is_flag=True, default=False, help="Enable Flask debug mode")
def serve(port, debug):
    """Start the Flask web server."""
    console.print()
    console.print(Panel.fit(
        f"[bold blue]🧬 DNA Report Generator[/bold blue] — Web Server\n"
        f"[dim]Open http://localhost:{port} in your browser[/dim]",
        border_style="blue",
    ))
    from app import app as flask_app
    flask_app.run(host="0.0.0.0", port=port, debug=debug)


# ── Helper: print summary table ───────────────────────────────────────────────
def _print_summary(report: dict):
    s = report["summary"]
    anc = report.get("ancestry", {})

    # Stats panel
    stats = Table(box=box.SIMPLE_HEAD, show_header=False, padding=(0, 2))
    stats.add_column("Key",   style="dim")
    stats.add_column("Value", style="bold")
    stats.add_row("Variants parsed",   str(s.get("total_variants", 0)))
    stats.add_row("Variants annotated",str(s.get("annotated_variants", 0)))
    stats.add_row("Pathogenic flags",  f"[red]{s.get('pathogenic_count', 0)}[/red]")
    stats.add_row("File format",       s.get("format", "—").upper())
    stats.add_row("Analysis mode",     s.get("mode", "—").title())
    stats.add_row("Top ancestry",      anc.get("top_population", "—"))
    stats.add_row("PGx findings",      str(len(report.get("pharmacogenomics", []))))
    stats.add_row("Trait findings",    str(len(report.get("traits", []))))

    console.print(Panel(stats, title="[bold]📊 Analysis Summary[/bold]", border_style="green"))

    # Risk scores
    risks = report.get("risk_scores", [])
    if risks:
        rtable = Table(title="Complex Disease Risk", box=box.ROUNDED, border_style="blue")
        rtable.add_column("Condition", style="bold")
        rtable.add_column("Risk Level")
        rtable.add_column("Lifetime Est.", justify="right")
        rtable.add_column("Relative Risk", justify="right")

        colors_map = {"high": "red", "elevated": "yellow", "average": "cyan", "below_average": "green"}
        for r in risks[:6]:
            c = colors_map.get(r["risk_tier"], "white")
            rtable.add_row(
                r["condition"],
                f"[{c}]{r['risk_label']}[/{c}]",
                f"{r['adjusted_risk_pct']}%",
                f"{r['relative_risk']}×",
            )
        console.print(rtable)

    # PGx
    pgx = report.get("pharmacogenomics", [])
    if pgx:
        ptable = Table(title="Pharmacogenomics", box=box.ROUNDED, border_style="yellow")
        ptable.add_column("Gene",    style="bold cyan")
        ptable.add_column("Variant")
        ptable.add_column("Drugs Affected")
        ptable.add_column("Severity")
        sev_color = {"high": "red", "moderate": "yellow", "low": "green"}
        for p in pgx:
            c = sev_color.get(p["severity"], "white")
            ptable.add_row(
                p["gene"], p["star_allele"],
                ", ".join(p["drugs_affected"][:2]),
                f"[{c}]{p['severity'].title()}[/{c}]",
            )
        console.print(ptable)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cli()
