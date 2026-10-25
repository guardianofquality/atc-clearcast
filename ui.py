"""Terminal UI using Rich for live ATC Flight Progress Strips."""

from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from tracker import FlightTracker, FlightStage, FlightType


STAGE_STYLES = {
    FlightStage.ENTERING: "bold cyan",
    FlightStage.READY_TAKEOFF: "bold yellow",
    FlightStage.CLEARED_TAKEOFF: "bold green",
    FlightStage.MANEUVERING: "blue",
    FlightStage.CLEARED_APPROACH: "magenta",
    FlightStage.CLEARED_LAND: "bold green",
    FlightStage.HANDOFF: "dim white",
}


class TerminalUI:
    """Renders the live Flight Strip Board in terminal using rich."""

    def __init__(self, tracker: FlightTracker):
        self.tracker = tracker
        self.console = Console()
        self.last_transmission: str = "System ready. Waiting for ATC traffic..."

    def set_last_transmission(self, text: str):
        self.last_transmission = text

    def build_table(self) -> Table:
        table = Table(title=f"✈  ACTIVE FLIGHT STRIPS — {self.tracker.airport_name.upper()}", expand=True)

        table.add_column("Callsign", style="bold white", width=10)
        table.add_column("Model", style="cyan", width=6, justify="center")
        table.add_column("Type", width=6, justify="center")
        table.add_column("Stage", width=12, justify="center")
        table.add_column("RWY", width=5, justify="center")
        table.add_column("ALT", width=7, justify="right")
        table.add_column("HDG", width=5, justify="right")
        table.add_column("Fix / Dest", width=10, style="magenta")
        table.add_column("Last Instruction", style="italic")
        table.add_column("Age", width=5, justify="right")

        strips = self.tracker.get_active_strips()
        if not strips:
            table.add_row("--", "--", "--", "NO TRAFFIC", "--", "--", "--", "--", "Listening for radio calls...", "--")
            return table

        for s in strips:
            stage_style = STAGE_STYLES.get(s.stage, "white")
            type_color = "cyan" if s.flight_type == FlightType.ARRIVAL else ("yellow" if s.flight_type == FlightType.DEPARTURE else "white")

            table.add_row(
                s.callsign,
                s.aircraft_model or "--",
                f"[{type_color}]{s.flight_type.value}[/{type_color}]",
                f"[{stage_style}]{s.stage.value}[/{stage_style}]",
                s.runway or "--",
                f"{s.altitude}ft" if s.altitude else "--",
                f"{s.heading}°" if s.heading else "--",
                s.destination_fix or "--",
                s.last_instruction[:35] + ("..." if len(s.last_instruction) > 35 else ""),
                s.formatted_age,
            )

        return table

    def render(self):
        """Prints a fresh snapshot of the board and latest radio transmission."""
        self.console.clear()
        table = self.build_table()
        panel = Panel(
            Text(f"Radio Comms: {self.last_transmission}", style="green"),
            title="Last Radio Transmission",
            border_style="bright_blue",
        )
        self.console.print(table)
        self.console.print(panel)
