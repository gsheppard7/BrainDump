"""Regenerate the sample PDFs in apps/api/seed and samples/.

Run: uv run python scripts/make_sample_files.py
"""

from datetime import UTC, datetime
from pathlib import Path

from fpdf import FPDF

FIXED_DATE = datetime(2026, 1, 1, tzinfo=UTC)

API_DIR = Path(__file__).resolve().parents[1]
SAMPLES_DIR = API_DIR.parents[1] / "samples"


def write_pdf(path: Path, title: str, pages: list[tuple[str, str]]) -> None:
    pdf = FPDF()
    pdf.set_title(title)
    pdf.set_creation_date(FIXED_DATE)
    for heading, body in pages:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.multi_cell(0, 10, heading)
        pdf.ln(2)
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(0, 6, body)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


def main() -> None:
    write_pdf(
        API_DIR / "seed" / "home-network-guide.pdf",
        "Home Network Setup Guide",
        [
            (
                "1. Overview",
                "This guide documents how the home network is set up so anyone in the house "
                "can troubleshoot it. The ISP modem is in bridge mode and the Eero mesh "
                "handles routing, DHCP and Wi-Fi.\n\n"
                "Main network: 'Sheppard-Home' (WPA3). Guest network: 'Sheppard-Guest', "
                "isolated from local devices. IoT devices (thermostat, robot vacuum, "
                "smart plugs) live on a separate 2.4 GHz SSID so they don't slow down "
                "laptops.",
            ),
            (
                "2. Mesh placement",
                "Primary node: office, wired to the modem. Second node: upstairs hallway on "
                "the bookshelf - keep it off the floor and away from the aquarium. Third "
                "node: garage, wired via the powerline adapter because the wireless "
                "backhaul through the concrete wall was unreliable.\n\n"
                "If speeds drop upstairs, check that the hallway node shows a 'great' "
                "connection in the app. Moving it 1-2 meters toward the stairs usually "
                "fixes it.",
            ),
            (
                "3. Troubleshooting checklist",
                "1) Is it one device or all devices? If one device, forget the network "
                "and rejoin.\n"
                "2) Check the ISP status page for outages before restarting anything.\n"
                "3) Restart order matters: modem first, wait two minutes, then the primary "
                "Eero, then the satellites.\n"
                "4) The printer needs a DHCP reservation (192.168.4.50) or AirPrint stops "
                "finding it.\n"
                "5) Firmware updates install automatically at 3am; occasional 3am "
                "disconnects are expected.",
            ),
        ],
    )
    write_pdf(
        SAMPLES_DIR / "reading-notes-systems-thinking.pdf",
        "Reading Notes - Systems Thinking",
        [
            (
                "Reading notes: systems thinking",
                "A system is a set of elements connected so that together they produce a "
                "pattern of behavior over time. The interesting part is rarely the elements; "
                "it is the interconnections and the purpose.\n\n"
                "Stocks and flows: a stock is anything that accumulates (water in a bathtub, "
                "money in savings, trust in a team). Flows change stocks. Stocks change "
                "slowly, which creates delays, buffers and the feeling that nothing is "
                "happening until suddenly everything is.",
            ),
            (
                "Feedback loops",
                "Balancing loops push a stock toward a goal (a thermostat). Reinforcing loops "
                "amplify change in either direction (compound interest, or a team losing "
                "people and overloading the rest).\n\n"
                "Leverage points: changing parameters (budgets, quotas) is the weakest "
                "lever. Changing feedback structure, information flows, or the goal of the "
                "system is much stronger.\n\n"
                "Personal takeaway: my overflowing inbox is a stock with an inflow I don't "
                "control. Reduce the inflow (unsubscribe, filters) instead of only trying "
                "to increase the outflow.",
            ),
        ],
    )
    blank = FPDF()
    blank.set_creation_date(FIXED_DATE)
    blank.add_page()
    blank.rect(20, 20, 170, 100)
    blank.output(str(SAMPLES_DIR / "scanned-receipt-no-text.pdf"))
    print("sample files written")


if __name__ == "__main__":
    main()
