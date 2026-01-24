"""
Jinja2 templates for prompt composition.

Templates are used to render context from memory layers into prompts.
"""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Template directory
TEMPLATE_DIR = Path(__file__).parent

# Jinja2 environment
_env = None


def get_template_env() -> Environment:
    """Get the Jinja2 template environment."""
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # Add custom filters
        _env.filters["format_price"] = format_price
        _env.filters["format_area"] = format_area
        _env.filters["format_distance"] = format_distance

    return _env


def format_price(value: int) -> str:
    """Format price in PLN (e.g., 700000 -> '700k zł')."""
    if value is None:
        return "nie określono"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f} mln zł"
    elif value >= 1000:
        return f"{value // 1000}k zł"
    else:
        return f"{value} zł"


def format_area(value: int) -> str:
    """Format area in m² (e.g., 1000 -> '1 000 m²')."""
    if value is None:
        return "nie określono"
    return f"{value:,} m²".replace(",", " ")


def format_distance(value: float) -> str:
    """Format distance in meters (e.g., 1500 -> '1.5 km')."""
    if value is None:
        return "brak danych"
    if value >= 1000:
        return f"{value / 1000:.1f} km"
    else:
        return f"{int(value)} m"


def render_template(template_name: str, context: dict) -> str:
    """Render a template with given context."""
    env = get_template_env()
    template = env.get_template(template_name)
    return template.render(**context)


def render_main_prompt(state_dict: dict) -> str:
    """Render the main agent prompt from state."""
    return render_template("main.j2", state_dict)


def render_skill_prompt(skill_name: str, context: dict) -> str:
    """Render a skill-specific prompt."""
    template_name = f"skills/{skill_name}.j2"
    return render_template(template_name, context)
