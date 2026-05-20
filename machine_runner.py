import argparse
import logging
import sys

import yaml
from machine.machine import ControlUnit, DataPath, IOController


def parse_schedule(input_file):
    parsed_schedule = None
    with open(input_file) as f:
        parsed_schedule = yaml.safe_load(f)

    if parsed_schedule is None or not isinstance(parsed_schedule, dict):
        parsed_schedule = {}

    input_schedule = parsed_schedule.get("in_ports", {})

    for port, events in input_schedule.items():
        for i, (tick, value) in enumerate(events):
            if isinstance(value, str) and len(value) == 1:
                input_schedule[port][i] = (tick, ord(value))
            elif isinstance(value, int):
                continue
            else:
                raise ValueError(f"Invalid input schedule value for port {port}: ({tick}, {value})")

    return input_schedule


def run_simulation(code_file, input_file, memory_size, tick_limit, verbose=False):
    logger = logging.getLogger(__name__)
    machine_code = None

    # parse input schedule

    input_schedule = {}
    if input_file:
        input_schedule = parse_schedule(input_file)

    # read compiled machine code
    with open(code_file, "rb") as f:
        machine_code = f.read()
    datapath = DataPath(memory_size)

    datapath.memory[0 : len(machine_code)] = machine_code

    io_controller = IOController(input_schedule=input_schedule)

    cu = ControlUnit(datapath, io_controller)

    # simulation
    while not cu.halt and cu.current_tick() < tick_limit:
        cu.process_next_tick()
        if verbose:
            logger.debug("%s", cu)

    if cu.current_tick() >= tick_limit:
        logger.warning("Tick limit exceeded")

    out_string = "".join(chr(b) if 0 <= b <= 127 else "?" for b in reversed(io_controller.out_ports[0]))
    print(out_string)
    print()
    print(f"ticks: {cu.current_tick()}")


def main():
    logging.basicConfig(level=logging.DEBUG, format="%(message)s", stream=sys.stdout)

    parser = argparse.ArgumentParser(prog="Machine", description="Machine model")
    parser.add_argument("source_path")
    parser.add_argument("-i", "--input_schedule_path")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-m", "--memory_size", type=int, default=64 * 1024, help="Memory size in bytes (default: 8192)")
    parser.add_argument("-l", "--tick_limit", type=int, default=10000, help="Simulation tick limit (default: 10000)")
    args = parser.parse_args()

    run_simulation(args.source_path, args.input_schedule_path, args.memory_size, args.tick_limit, args.verbose)


if __name__ == "__main__":
    main()
