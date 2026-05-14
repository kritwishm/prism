import asyncio
from typing import Optional

import typer
from loguru import logger

from prism.pipeline import run_pipeline

app = typer.Typer(help="Prism — account research → personalized content pipeline")


def _normalize(url: str) -> str:
    return url if url.startswith(("http://", "https://")) else f"https://{url}"


@app.command()
def analyze(
    url: str = typer.Argument(..., help="Company URL"),
    dump: Optional[str] = typer.Option(
        None, "--dump", help="Directory to write a JSON snapshot of this run"
    ),
):
    """Run the pipeline for one company URL."""
    result = asyncio.run(run_pipeline(_normalize(url), dump_dir=dump))
    if not result["success"]:
        raise typer.Exit(code=1)


@app.command()
def batch(
    urls_file: str = typer.Argument(..., help="File with one URL per line"),
    dump: Optional[str] = typer.Option(
        None, "--dump", help="Directory to write per-run JSON snapshots"
    ),
):
    """Run the pipeline on multiple URLs."""
    with open(urls_file) as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    for url in urls:
        try:
            asyncio.run(run_pipeline(_normalize(url), dump_dir=dump))
        except Exception as e:
            logger.error(f"failed {url}: {e}")
            continue


if __name__ == "__main__":
    app()
