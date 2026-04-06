"""Board search and filtering."""

from pathlib import Path

from dbf.data import load_all_boards


def load_boards(boards_dir: Path) -> list[dict]:
    """Load all boards from a directory."""
    return load_all_boards(boards_dir)


def search_boards(
    boards: list[dict],
    wifi: bool = False,
    bluetooth: bool = False,
    rust: bool = False,
    manufacturer: str | None = None,
    board_type: str | None = None,
    architecture: str | None = None,
    framework: str | None = None,
    language: str | None = None,
    difficulty: str | None = None,
    min_ram_kb: int | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """Filter boards by criteria. All filters are AND-ed together."""
    results = list(boards)

    if wifi:
        results = [b for b in results if _has_wireless(b, "wifi")]

    if bluetooth:
        results = [b for b in results if _has_wireless(b, "bluetooth") or _has_wireless(b, "ble")]

    if rust:
        results = [b for b in results if _has_language(b, "rust")]

    if manufacturer:
        results = [b for b in results if manufacturer.lower() in b.get("manufacturer", "").lower()]

    if board_type:
        results = [b for b in results if board_type in b.get("board_type", [])]

    if architecture:
        results = [b for b in results if _has_architecture(b, architecture)]

    if framework:
        results = [
            b for b in results
            if any(
                framework.lower() in f.get("name", "").lower()
                for f in b.get("software", {}).get("frameworks", [])
            )
        ]

    if language:
        results = [b for b in results if _has_language(b, language)]

    if difficulty:
        results = [b for b in results if b.get("difficulty_level") == difficulty]

    if min_ram_kb is not None:
        results = [b for b in results if _get_ram_kb(b) >= min_ram_kb]

    if max_price is not None:
        results = [
            b for b in results
            if b.get("pricing", {}).get("msrp_usd") is not None
            and b["pricing"]["msrp_usd"] <= max_price
        ]

    return results


def _has_wireless(board: dict, protocol: str) -> bool:
    return any(
        protocol.lower() in w.get("protocol", "").lower()
        for w in board.get("wireless", [])
    )


def _has_language(board: dict, language: str) -> bool:
    return any(
        language.lower() == l.get("name", "").lower()
        for l in board.get("software", {}).get("languages", [])
    )


def _has_architecture(board: dict, arch: str) -> bool:
    arch_lower = arch.lower()
    for pe in board.get("processing", []):
        for core in pe.get("cpu_cores", []):
            if arch_lower in core.get("architecture", "").lower():
                return True
    return False


def _get_ram_kb(board: dict) -> int:
    """Get total RAM in KB from the first processing element."""
    for pe in board.get("processing", []):
        mem = pe.get("memory", {})
        ram = mem.get("ram_kb")
        if ram is not None:
            return ram
    return 0
