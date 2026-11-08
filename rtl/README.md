# RTL

Synthesizable board-independent processing belongs in `core/`; protocol adapters belong in `axi/`; UPduino-specific clocking, memories, pins, and wrappers belong in `board/`. Simulation-only public-interface checks belong in `assertions/` and are excluded from implementation builds.
