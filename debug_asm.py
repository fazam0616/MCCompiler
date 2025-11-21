"""
Debug runner for MCL assembly files.

This script loads an assembly file, executes it step-by-step in the virtual machine,
and prints the state of all non-zero registers after each instruction.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from vm.virtual_machine import create_vm
from vm.assembly_loader import load_assembly_file
from vm.cpu import CPUState

def run_and_debug(asm_file: str):
    """
    Runs an assembly file step-by-step and prints register states.
    """
    print(f"--- Debugging {asm_file} ---")

    # Create a headless VM
    config = {'enable_gpu': False}
    vm = create_vm(config)

    # Load assembly file
    try:
        # instructions, labels = load_assembly_file(asm_file)
        vm.load_program(asm_file)
        vm.cpu.set_labels(vm.memory.labels)
    except Exception as e:
        print(f"Error loading assembly: {e}")
        return

    # Run step-by-step
    vm.cpu.state = CPUState.RUNNING
    step_count = 0
    max_steps = 100 # Safety break to prevent infinite loops

    header_printed = False

    while vm.cpu.state == CPUState.RUNNING and step_count < max_steps:
        pc_before = vm.cpu.pc
        
        try:
            instruction = vm.memory.fetch_instruction(pc_before)
        except IndexError:
            print("\nExecution stopped: PC out of bounds.")
            break

        if not instruction:
            print("\nEnd of program.")
            break

        if not header_printed:
            print(f"{'Step':<5} {'PC':<5} {'Instruction':<25} {'Relevant Registers'}")
            print("-" * 60)
            header_printed = True

        # Execute the instruction
        vm.cpu.step()

        # Prepare output
        step_str = f"{step_count:<5}"
        pc_str = f"{pc_before:<5}"
        instr_str = f"{instruction.opcode} {', '.join(map(str, instruction.operands))}"
        instr_str = f"{instr_str:<25}"

        reg_states = []
        for i in range(32):  # Assuming 32 registers as per cpu.py
            val = vm.cpu.get_register(i)
            if val != 0:
                reg_states.append(f"R{i}={val}")
        
        reg_str = ", ".join(reg_states) if reg_states else "(all zero)"

        print(f"{step_str} {pc_str} {instr_str} {reg_str}")
        
        step_count += 1

    print("-" * 60)
    print("--- Execution Finished ---")
    final_state = vm.cpu.get_state()
    print(f"Halt Reason: {final_state['halt_reason']}")
    print(f"Final Return Value (R0): {final_state['registers'][0]}")


if __name__ == "__main__":
    # Default to params.asm if no argument is given
    file_to_debug = "params.asm"
    if len(sys.argv) > 1:
        file_to_debug = sys.argv[1]
    
    if not Path(file_to_debug).exists():
        print(f"Error: File '{file_to_debug}' not found.")
    else:
        run_and_debug(file_to_debug)
