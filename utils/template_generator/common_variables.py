enclosed_variable_pattern = r'^{([^}]*)}$|^<([^>]*)>$|^\(([^)]*)\)$|^\[([^\]]*)\]$'
ordered_variable_pattern = r'(\w+)\[(\d+)\]$'
variable_pattern = r'\{\{(.*?)\}\}'
template_path_variable = r'^\w+(\[\d+\])?(\.\w+(\[\d+\])?)*$'