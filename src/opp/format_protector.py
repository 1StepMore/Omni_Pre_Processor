from typing import List, Dict, Any


class FormatProtector:
    def detect_code_blocks(self, text: str) -> Dict[str, Any]:
        import re
        blocks = []
        fenced_ranges = []
        lines = text.split('\n')
        char_pos = 0
        i = 0
        while i < len(lines):
            line = lines[i]
            line_len = len(line) + (1 if i < len(lines) - 1 else 0)
            is_fence_start = line.strip().startswith(('```', '~~~'))
            if is_fence_start and not self._in_string_context(lines, i):
                fence_type = line.strip()[:3]
                language = line.strip()[3:].strip() or None
                fence_start_char = char_pos
                content_lines = []
                char_pos += len(line) + 1
                i += 1
                found_closing = False
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.strip() == fence_type and not self._in_string_context(lines, i):
                        found_closing = True
                        break
                    content_lines.append(next_line)
                    char_pos += len(next_line) + 1
                    i += 1
                if found_closing:
                    content = '\n'.join(content_lines)
                    if content.strip() or language:
                        blocks.append({
                            'type': 'fenced',
                            'content': content.strip(),
                            'language': language
                        })
                        fence_end_char = char_pos + len(lines[i]) if i < len(lines) else char_pos
                        fenced_ranges.append((fence_start_char, fence_end_char))
                    char_pos += len(lines[i]) + 1
                    i += 1
                else:
                    char_pos += len(line) + 1
            else:
                char_pos += len(line) + 1
                i += 1

        line_ranges = []
        search_start = 0
        for line in text.split('\n'):
            pos = text.find(line, search_start)
            line_ranges.append((pos, pos + len(line), line))
            search_start = pos + len(line)

        current_indent_block = None
        for line_start, line_end, line in line_ranges:
            in_fenced = any(start <= line_start < end for start, end in fenced_ranges)
            if not in_fenced and (line.startswith('    ') or line.startswith('\t')):
                stripped = line.lstrip()
                if any(char in stripped for char in '{};()[]'):
                    if current_indent_block is None:
                        current_indent_block = {
                            'type': 'indented',
                            'content': stripped,
                            'language': None
                        }
                    else:
                        current_indent_block['content'] += '\n' + stripped
            else:
                if current_indent_block is not None:
                    blocks.append(current_indent_block)
                    current_indent_block = None

        if current_indent_block is not None:
            blocks.append(current_indent_block)

        single_pattern = r'`([^`]+)`'
        for match in re.finditer(single_pattern, text):
            if not any(start <= match.start() < end for start, end in fenced_ranges):
                content = match.group(1)
                if any(c in content for c in '(){}=;<>') or content.startswith(('def ', 'class ', 'import ', 'from ')):
                    blocks.append({
                        'type': 'single',
                        'content': content,
                        'language': None
                    })

        return {'has_code': len(blocks) > 0, 'blocks': blocks}

    def _in_string_context(self, lines: List[str], line_idx: int) -> bool:
        in_string = False
        for i in range(line_idx):
            line = lines[i]
            j = 0
            while j < len(line):
                if line[j] == '"' and (j == 0 or line[j-1] != '\\'):
                    in_string = not in_string
                    j += 1
                elif line[j] == '\\':
                    j += 2
                else:
                    j += 1
        return in_string

    def protect_special_chars(self, text: str) -> str:
        import re

        blocks = []

        fenced_pattern = r'(```|~~~)(\w*)\n(.*?)(\1)'
        for match in re.finditer(fenced_pattern, text, re.DOTALL):
            fence_type, language, content, _ = match.groups()
            blocks.append({
                'type': 'fenced',
                'content': content.strip(),
                'language': language if language else None,
                'original': match.group(0)
            })

        for line in text.split('\n'):
            if line.startswith('    ') or line.startswith('\t'):
                stripped = line.lstrip()
                if any(char in stripped for char in '{};()[]'):
                    blocks.append({
                        'type': 'indented',
                        'content': stripped,
                        'original': line
                    })

        single_pattern = r'`([^`]+)`'
        for match in re.finditer(single_pattern, text):
            content = match.group(1)
            if any(c in content for c in '(){}=;<>') or content.startswith(('def ', 'class ', 'import ', 'from ')):
                blocks.append({
                    'type': 'single',
                    'content': content,
                    'original': match.group(0)
                })

        protected_text = text
        for i, block in enumerate(blocks):
            placeholder = f"<<<CODE{i}>>>"
            protected_text = protected_text.replace(block['original'], placeholder)

        special_chars = ['\\', '*', '_', '[', ']', '(', ')', '#', '+', '-', '.', '!', '|']
        for char in special_chars:
            protected_text = protected_text.replace(char, '\\' + char)

        result = protected_text
        for i, block in enumerate(blocks):
            result = result.replace(f"<<<CODE{i}>>>", block['original'])

        return result