def bit_to_hex(bit_number, extra_bit1=None, extra_bit2=None):
    # Adjust for 1-based input (1-128) to 0-based indexing (0-127)
    bit_number = bit_number - 1
    # Validate bit number
    if not isinstance(bit_number, int) or bit_number < 0 or bit_number > 127:
        return "Error: Bit number must be an integer between 1 and 128"

    # Validate extra bit numbers (1-128, or None, 1-based)
    if extra_bit1 is not None:
        extra_bit1 = extra_bit1 - 1  # Convert to 0-based
        if not isinstance(extra_bit1, int) or extra_bit1 < 0 or extra_bit1 > 127:
            return "Error: Extra bit 1 must be an integer between 1 and 128"
    if extra_bit2 is not None:
        extra_bit2 = extra_bit2 - 1  # Convert to 0-based
        if not isinstance(extra_bit2, int) or extra_bit2 < 0 or extra_bit2 > 127:
            return "Error: Extra bit 2 must be an integer between 1 and 128"

    # Calculate value by setting specified bits
    value = 1 << bit_number  # Set primary bit
    if extra_bit1 is not None:
        value |= 1 << extra_bit1  # Set extra bit 1
    if extra_bit2 is not None:
        value |= 1 << extra_bit2  # Set extra bit 2

    # Convert to hex using a while loop
    hex_digits = "0123456789abcdef"
    hex_result = ""
    temp = value
    while temp > 0:
        digit = temp & 0xF  # Get last 4 bits
        hex_result = hex_digits[digit] + hex_result
        temp >>= 4  # Shift right by 4 bits
    if not hex_result:
        hex_result = "0"

    # Pad to 32 characters (128 bits = 32 hex digits)
    hex_result = "0" * (32 - len(hex_result)) + hex_result

    return hex_result


# Main program
while True:
    try:
        user_input = input(
            "Enter bit number (1-128) and 0-2 extra bits to set (1-128), separated by spaces (or 'q' to quit): ")
        if user_input.lower() == 'q':
            break

        # Split input into parts
        parts = user_input.split()
        if len(parts) not in [1, 2, 3]:
            print(
                "Error: Enter bit number alone or bit number followed by one or two extra bits to set, separated by spaces")
            continue

        # Parse bit number
        bit_number = int(parts[0])

        # Parse extra bit numbers (if provided)
        extra_bit1 = None
        extra_bit2 = None
        if len(parts) >= 2:
            extra_bit1 = int(parts[1])
        if len(parts) == 3:
            extra_bit2 = int(parts[2])

        # Get result
        result = bit_to_hex(bit_number, extra_bit1, extra_bit2)

        # Print result with clear description
        extra_info = ""
        if extra_bit1 is not None and extra_bit2 is not None:
            extra_info = f", extra bits {extra_bit1} and {extra_bit2} set"
        elif extra_bit1 is not None:
            extra_info = f", extra bit {extra_bit1} set"
        print(
            f"Input bit {bit_number} (1-based LSB, maps to bit {bit_number - 1} 0-based){extra_info} corresponds to: {result}")
    except ValueError:
        print("Error: Please enter valid integers (bit: 1-128, extra bits: 1-128) or 'q' to quit")