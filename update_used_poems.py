from db_upsert_entity import update_entry


def read_file_to_blocks(filename):
    with open(filename, 'r') as file:
        content = file.read()

    # Split the content by one or more newline characters to handle multiple empty lines as separators
    blocks = content.strip().split("\n\n\n")

    # Further split each block by newline to get arrays of strings
    arrays_of_strings = [block.split("\n") for block in blocks]

    return arrays_of_strings

# Example usage
filename = "/home/mpshater/images/guids_to_update.txt"  # Replace with your actual file path
blocks_as_arrays = read_file_to_blocks(filename)

update_entry(blocks_as_arrays[1], 'ru')
update_entry(blocks_as_arrays[0], 'ua')
update_entry(blocks_as_arrays[2], 'en')
