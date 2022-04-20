"""Cli tool to handle revelation commands"""

import glob
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from typer import Option
from typer.main import get_command
from werkzeug.serving import run_simple

import revelation
from revelation import Revelation
from revelation.constants import (
    MATHJAX_DIR,
    MATHJAX_URL,
    REVEAL_URL,
    REVEALJS_DIR,
)
from revelation.utils import (
    download_file,
    extract_file,
    make_presentation,
    move_and_replace,
)

cli = typer.Typer()
echo = typer.echo


def error(message: str):
    typer.secho(f"Error: {message}", err=True, fg="red", bold=True)


def revelation_factory(
    presentation: Path,
    config: Optional[Path] = None,
    media: Optional[Path] = None,
    theme: Optional[Path] = None,
    style: Optional[Path] = None,
    scripts: Optional[Path] = None,
    update: Optional[bool] = True,
) -> Revelation:
    if presentation.is_file():
        path = presentation.parent
    else:
        error("Presentation file not found.")

        raise typer.Abort()

    if style:
        for st in style:
            if (not st.is_file() or not st.suffix == ".css"):
                error("Style is not a css file or does not exists.")
                raise typer.Abort()

    if not media:
        media = path / "media"

    if not media.is_dir():
        media = None

        echo("Media folder not detected, running without media.")

    if not theme:
        theme = path / "theme"

    if not theme.is_dir():
        theme = None

        echo("Theme not detected, running without custom theme.")

    if not config:
        config = path / "config.py"

    if config and not config.is_file():
        config = None

        echo("Configuration file not detected, running with defaults.")

    if not scripts:
        scripts = path / "scripts"

    if not scripts.is_dir():
        scripts = None
        echo("No extra scripts/plugins detected")

    return Revelation(presentation, config, media, theme, style, scripts, update)


@cli.command()
def version():
    """
    Show version
    """
    echo(revelation.__version__)


@cli.command()
def installreveal(
    url: str = Option(REVEAL_URL, "--url", "-u", help="Reveal.js download url")
):
    """
    Install or upgrade reveal.js dependency

    Receives the download url to install from a specific version or
    downloads the latest version if noting is passed
    """
    echo("Downloading reveal.js...")

    download = download_file(url)

    echo("Installing reveal.js...")

    move_and_replace(extract_file(download[0]), REVEALJS_DIR)

    echo("Downloading MathJax...")

    download = download_file(MATHJAX_URL)

    echo("Installing MathJax...")

    move_and_replace(extract_file(download[0]), MATHJAX_DIR)

    echo("Installation completed!")


@cli.command()
def mkpresentation(presentation: Path):
    """Create a new revelation presentation"""
    if presentation.exists():
        error(f"'{presentation}' already exists.")

        raise typer.Abort()

    echo("Starting a new presentation...")

    make_presentation(presentation)


@cli.command()
def mkstatic(
    ctx: typer.Context,
    presentation: Path,
    config: Optional[Path] = Option(
        None, "--config", "-c", help="Custom config file"
    ),
    media: Optional[Path] = Option(
        None, "--media", "-m", help="Custom media folder"
    ),
    theme: Optional[Path] = Option(
        None, "--theme", "-t", help="Custom theme folder"
    ),
    scripts: Optional[Path] = Option(
        None, "--scripts", "-r", help="Directory with extra javascript plugins"
    ),
    output_folder: Path = Option(
        Path("output"),
        "--output-folder",
        "-o",
        help="Folder where the static presentation will be generated",
    ),
    output_file: Path = Option(
        Path("index.html"),
        "--output-file",
        "-f",
        help="File name of the static presentation",
    ),
    force: bool = Option(
        False,
        "--force",
        "-r",
        help="Overwrite the output folder if exists",
    ),
    style: Optional[list[Path]] = Option(
        None,
        "--style-override-file",
        "-s",
        help="Custom css file to override reveal.js styles",
    ),
    update: Optional[bool] = Option(
        False,
        "--update",
        "-u",
        help="Update or overwrite default config"
    ),

):
    """Make static presentation"""

    if not REVEALJS_DIR.exists():
        echo("Reveal.js not found, running installation...")

        # Change after fix on https://github.com/tiangolo/typer/issues/102
        ctx.invoke(
            get_command(cli).get_command(ctx, "installreveal")  # type: ignore
        )

    if output_folder.is_dir():
        if force:
            shutil.rmtree(output_folder)
        else:
            error(
                f"'{output_folder}' already exists, "
                "use --force to override it."
            )

            raise typer.Abort()

    if output_folder.is_file():
        error(f"'{output_folder}' already exists and is a file.")

        raise typer.Abort()

    app = revelation_factory(presentation, config, media, theme, style, scripts, update)

    echo("Generating static presentation...")

    staticfolder = output_folder / "static"

    output_folder.mkdir(parents=True, exist_ok=True)

    if app.style:
        for st in app.style:
            shutil.copy(st, output_folder / st.name)

    shutil.copytree(REVEALJS_DIR, staticfolder / "revealjs")
    shutil.copytree(MATHJAX_DIR, staticfolder / "mathjax")

    if app.media:
        shutil.copytree(app.media, output_folder / shutil.os.path.basename(app.media))

    if app.theme:
        shutil.copytree(app.theme, output_folder / "theme")

    if app.scripts:
        shutil.copytree(app.scripts, output_folder / app.scripts)

    output_folder = output_folder.resolve()

    if not output_folder.is_dir():
        output_folder.mkdir(parents=True, exist_ok=True)

    output_file = output_folder / output_file

    with output_file.open("wb") as fp:
        fp.write(app.dispatch_request().get_data(as_text=True).encode("utf-8"))

    echo(f"Static presentation generated in {output_folder}")


@cli.command()
def start(
    ctx: typer.Context,
    presentation: Path,
    port: int = Option(4000, "--port", "-p", help="Presentation server port"),
    config: Optional[Path] = Option(
        None, "--config", "-c", help="Custom config file"
    ),
    media: Optional[Path] = Option(
        None, "--media", "-m", help="Custom media folder"
    ),
    theme: Optional[Path] = Option(
        None, "--theme", "-t", help="Custom theme folder"
    ),
    scripts: Optional[Path] = Option(
        None, "--scripts", "-r", help="Custom javascript plugin folder"
    ),
    style: Optional[list[Path]] = Option(
        None,
        "--style-override-file",
        "-s",
        help="Custom css file to override reveal.js styles",
    ),
    debug: bool = Option(
        False,
        "--debug",
        "-d",
        is_flag=True,
        help="Run the revelation server on debug mode",
    ),
    update: Optional[bool] = Option(
        False,
        "--update",
        "-u",
        help="Update or overwrite default config"
    ),
):
    """Start the revelation server"""

    if not REVEALJS_DIR.exists():
        echo("Reveal.js not found, running installation...")

        # Change after fix on https://github.com/tiangolo/typer/issues/102
        ctx.invoke(
            get_command(cli).get_command(ctx, "installreveal")  # type: ignore
        )

    app = revelation_factory(presentation, config, media, theme, style, scripts, update)

    presentation_root = presentation.parent

    echo("Starting revelation server...")

    server_args: Dict[str, Any] = {
        "hostname": "localhost",
        "port": port,
        "application": app,
        "use_reloader": False,
    }

    if debug:
        server_args["use_debugger"] = True
        server_args["use_reloader"] = True
        server_args["reloader_type"] = "watchdog"
        server_args["extra_files"] = glob.glob(
            str(presentation_root / "*.md")
        ) + glob.glob(str(presentation_root / "*.css"))

    run_simple(**server_args)
