def bit_to_hex(bit_number):
    # Adjust for 1-based input (1-128) to 0-based indexing (0-127)
    bit_number = bit_number - 1
    # Validate input
    if not isinstance(bit_number, int) or bit_number < 0 or bit_number > 127:
        return "Error: Bit number must be an integer between 1 and 128"

    # Calculate 2^bit_number
    value = 1 << bit_number

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

    # Return hex without 0x prefix
    return hex_result


# Main program
while True:
    try:
        bit_input = input("Enter bit number (1-128, or 'q' to quit): ")
        if bit_input.lower() == 'q':
            break
        bit_number = int(bit_input)
        result = bit_to_hex(bit_number)
        print(f"Input bit {bit_number} (1-based LSB, maps to bit {bit_number - 1} 0-based) corresponds to: {result}")
    except ValueError:
        print("Error: Please enter a valid integer or 'q' to quit")