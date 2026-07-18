"""
Arova Native Markdown Renderer

Renders a Phase 1 markdown subset into Gtk.TextView using semantic TextBuffer tags.
Supports: headings, bold, italic, inline code, code blocks, lists, blockquotes, links.

Architecture:
    markdown string → parse_to_blocks() → list[MarkdownBlock]
    list[MarkdownBlock] → render_to_textview() → Gtk.TextView with styled tags
"""

import re
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Pango, GLib
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum, auto


class BlockType(Enum):
    PARAGRAPH = auto()
    HEADING = auto()
    CODE_BLOCK = auto()
    BLOCKQUOTE = auto()
    UNORDERED_LIST = auto()
    ORDERED_LIST = auto()
    HORIZONTAL_RULE = auto()


@dataclass
class InlineSpan:
    """A segment of inline text with formatting."""
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    link_url: Optional[str] = None


@dataclass
class MarkdownBlock:
    """A parsed block of markdown content."""
    block_type: BlockType
    content: str = ""
    level: int = 1  # heading level, list indent
    language: str = ""  # code block language
    spans: List[InlineSpan] = field(default_factory=list)
    items: List[str] = field(default_factory=list)  # list items


# ─── Inline Parser ───────────────────────────────────────────────────────

_INLINE_PATTERNS = [
    # Order matters: bold+italic before bold before italic
    (r'\*\*\*(.+?)\*\*\*', {'bold': True, 'italic': True}),
    (r'\*\*(.+?)\*\*', {'bold': True}),
    (r'\*(.+?)\*', {'italic': True}),
    (r'`(.+?)`', {'code': True}),
    (r'\[([^\]]+)\]\(([^)]+)\)', 'link'),
]


def _parse_inline(text: str) -> List[InlineSpan]:
    """Parse inline markdown formatting into a list of InlineSpan."""
    spans = []
    
    # Build a combined regex that captures all inline patterns
    # We process left-to-right, consuming text as we go
    pos = 0
    while pos < len(text):
        earliest_match = None
        earliest_start = len(text)
        matched_style = None
        
        for pattern, style in _INLINE_PATTERNS:
            m = re.search(pattern, text[pos:])
            if m and (pos + m.start()) < earliest_start:
                earliest_match = m
                earliest_start = pos + m.start()
                matched_style = style
        
        if earliest_match is None:
            # No more inline formatting — emit rest as plain text
            remaining = text[pos:]
            if remaining:
                spans.append(InlineSpan(text=remaining))
            break
        
        # Emit plain text before the match
        if earliest_start > pos:
            spans.append(InlineSpan(text=text[pos:earliest_start]))
        
        if matched_style == 'link':
            spans.append(InlineSpan(
                text=earliest_match.group(1),
                link_url=earliest_match.group(2)
            ))
        else:
            spans.append(InlineSpan(
                text=earliest_match.group(1),
                **matched_style
            ))
        
        pos = earliest_start + len(earliest_match.group(0))
    
    return spans if spans else [InlineSpan(text=text)]


# ─── Block Parser ────────────────────────────────────────────────────────

def parse_to_blocks(markdown: str) -> List[MarkdownBlock]:
    """Parse a markdown string into a list of MarkdownBlock."""
    blocks = []
    lines = markdown.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Code block (fenced)
        if line.strip().startswith('```'):
            lang = line.strip()[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            blocks.append(MarkdownBlock(
                block_type=BlockType.CODE_BLOCK,
                content='\n'.join(code_lines),
                language=lang
            ))
            continue
        
        # Heading
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            blocks.append(MarkdownBlock(
                block_type=BlockType.HEADING,
                content=content,
                level=level,
                spans=_parse_inline(content)
            ))
            i += 1
            continue
        
        # Horizontal rule
        if re.match(r'^(-{3,}|\*{3,}|_{3,})\s*$', line.strip()):
            blocks.append(MarkdownBlock(block_type=BlockType.HORIZONTAL_RULE))
            i += 1
            continue
        
        # Blockquote
        if line.strip().startswith('>'):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith('>'):
                quote_lines.append(re.sub(r'^>\s?', '', lines[i]))
                i += 1
            content = '\n'.join(quote_lines)
            blocks.append(MarkdownBlock(
                block_type=BlockType.BLOCKQUOTE,
                content=content,
                spans=_parse_inline(content)
            ))
            continue
        
        # Unordered list
        if re.match(r'^\s*[-*+]\s+', line):
            items = []
            while i < len(lines) and re.match(r'^\s*[-*+]\s+', lines[i]):
                item_text = re.sub(r'^\s*[-*+]\s+', '', lines[i])
                items.append(item_text)
                i += 1
            blocks.append(MarkdownBlock(
                block_type=BlockType.UNORDERED_LIST,
                items=items
            ))
            continue
        
        # Ordered list
        if re.match(r'^\s*\d+\.\s+', line):
            items = []
            while i < len(lines) and re.match(r'^\s*\d+\.\s+', lines[i]):
                item_text = re.sub(r'^\s*\d+\.\s+', '', lines[i])
                items.append(item_text)
                i += 1
            blocks.append(MarkdownBlock(
                block_type=BlockType.ORDERED_LIST,
                items=items
            ))
            continue
        
        # Empty line
        if not line.strip():
            i += 1
            continue
        
        # Paragraph (collect consecutive non-empty lines)
        para_lines = []
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('#') \
                and not lines[i].strip().startswith('```') and not lines[i].strip().startswith('>') \
                and not re.match(r'^\s*[-*+]\s+', lines[i]) \
                and not re.match(r'^\s*\d+\.\s+', lines[i]) \
                and not re.match(r'^(-{3,}|\*{3,}|_{3,})\s*$', lines[i].strip()):
            para_lines.append(lines[i])
            i += 1
        content = ' '.join(para_lines)
        if content:
            blocks.append(MarkdownBlock(
                block_type=BlockType.PARAGRAPH,
                content=content,
                spans=_parse_inline(content)
            ))
    
    return blocks


# ─── GTK Renderer ─────────────────────────────────────────────────────────

class MarkdownTextView(Gtk.Box):
    """
    A Gtk.Box containing a non-editable Gtk.TextView that renders markdown
    with semantic tags. Designed for the Arova chat surface.
    """
    
    # Color palette — Arova emotional design tokens
    COLORS = {
        'text':       'rgba(230, 235, 245, 0.92)',
        'text_dim':   'rgba(180, 190, 210, 0.7)',
        'heading':    'rgba(245, 248, 255, 0.95)',
        'code_fg':    'rgba(200, 220, 255, 0.9)',
        'code_bg':    'rgba(255, 255, 255, 0.06)',
        'quote_bar':  'rgba(120, 140, 255, 0.5)',
        'quote_fg':   'rgba(190, 200, 225, 0.8)',
        'link':       'rgba(100, 180, 255, 0.9)',
        'list_bullet':'rgba(120, 160, 255, 0.7)',
    }
    
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        self._textview = Gtk.TextView()
        self._textview.set_editable(False)
        self._textview.set_cursor_visible(False)
        self._textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._textview.set_top_margin(8)
        self._textview.set_bottom_margin(8)
        self._textview.set_left_margin(12)
        self._textview.set_right_margin(12)
        self._textview.add_css_class("md-textview")
        
        self._buffer = self._textview.get_buffer()
        self._setup_tags()
        
        self.append(self._textview)
    
    def _setup_tags(self):
        """Create all semantic tags for the TextBuffer."""
        table = self._buffer.get_tag_table()
        
        # Headings
        for level in range(1, 7):
            sizes = [20, 17, 15, 14, 13, 12]  # Pango points
            tag = self._buffer.create_tag(
                f"h{level}",
                weight=Pango.Weight.BOLD,
                size_points=sizes[level - 1],
                foreground=self.COLORS['heading'],
                pixels_above_lines=12 if level <= 2 else 8,
                pixels_below_lines=6,
            )
        
        # Inline styles
        self._buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self._buffer.create_tag("italic", style=Pango.Style.ITALIC)
        self._buffer.create_tag(
            "inline_code",
            family="JetBrains Mono, Fira Code, monospace",
            foreground=self.COLORS['code_fg'],
            background=self.COLORS['code_bg'],
            size_points=12,
        )
        self._buffer.create_tag(
            "link",
            foreground=self.COLORS['link'],
            underline=Pango.Underline.SINGLE,
        )
        
        # Code block
        self._buffer.create_tag(
            "code_block",
            family="JetBrains Mono, Fira Code, monospace",
            foreground=self.COLORS['code_fg'],
            paragraph_background=self.COLORS['code_bg'],
            size_points=12,
            pixels_above_lines=8,
            pixels_below_lines=8,
            left_margin=20,
            right_margin=20,
        )
        
        # Blockquote
        self._buffer.create_tag(
            "blockquote",
            foreground=self.COLORS['quote_fg'],
            style=Pango.Style.ITALIC,
            left_margin=24,
            pixels_above_lines=4,
            pixels_below_lines=4,
        )
        
        # List
        self._buffer.create_tag(
            "list_item",
            left_margin=24,
            pixels_above_lines=2,
            pixels_below_lines=2,
        )
        self._buffer.create_tag(
            "list_bullet",
            foreground=self.COLORS['list_bullet'],
            weight=Pango.Weight.BOLD,
        )
        
        # Body text
        self._buffer.create_tag(
            "body",
            foreground=self.COLORS['text'],
            size_points=13,
            pixels_above_lines=3,
            pixels_below_lines=3,
        )
        
        # Horizontal rule
        self._buffer.create_tag(
            "hr",
            foreground=self.COLORS['text_dim'],
            size_points=6,
            pixels_above_lines=8,
            pixels_below_lines=8,
        )
    
    def render(self, markdown: str):
        """Parse and render markdown into the TextView."""
        self._buffer.set_text("")
        blocks = parse_to_blocks(markdown)
        
        for i, block in enumerate(blocks):
            if i > 0:
                self._insert_newline()
            self._render_block(block)
    
    def append_text(self, markdown: str):
        """Append markdown to the existing content (for streaming)."""
        blocks = parse_to_blocks(markdown)
        for block in blocks:
            self._insert_newline()
            self._render_block(block)
        
        # Auto-scroll to bottom
        GLib.idle_add(self._scroll_to_bottom)
    
    def _scroll_to_bottom(self):
        end = self._buffer.get_end_iter()
        self._textview.scroll_to_iter(end, 0.0, False, 0.0, 1.0)
        return False
    
    def _insert_newline(self):
        end = self._buffer.get_end_iter()
        self._buffer.insert(end, "\n")
    
    def _render_block(self, block: MarkdownBlock):
        if block.block_type == BlockType.HEADING:
            self._render_heading(block)
        elif block.block_type == BlockType.PARAGRAPH:
            self._render_paragraph(block)
        elif block.block_type == BlockType.CODE_BLOCK:
            self._render_code_block(block)
        elif block.block_type == BlockType.BLOCKQUOTE:
            self._render_blockquote(block)
        elif block.block_type in (BlockType.UNORDERED_LIST, BlockType.ORDERED_LIST):
            self._render_list(block)
        elif block.block_type == BlockType.HORIZONTAL_RULE:
            self._render_hr()
    
    def _render_heading(self, block: MarkdownBlock):
        tag_name = f"h{block.level}"
        end = self._buffer.get_end_iter()
        self._buffer.insert_with_tags_by_name(end, block.content, tag_name)
    
    def _render_paragraph(self, block: MarkdownBlock):
        self._render_spans(block.spans, "body")
    
    def _render_spans(self, spans: List[InlineSpan], base_tag: str = "body"):
        for span in spans:
            tags = [base_tag]
            if span.bold:
                tags.append("bold")
            if span.italic:
                tags.append("italic")
            if span.code:
                tags.append("inline_code")
            if span.link_url:
                tags.append("link")
            
            end = self._buffer.get_end_iter()
            self._buffer.insert_with_tags_by_name(end, span.text, *tags)
    
    def _render_code_block(self, block: MarkdownBlock):
        end = self._buffer.get_end_iter()
        self._buffer.insert_with_tags_by_name(end, block.content, "code_block")
    
    def _render_blockquote(self, block: MarkdownBlock):
        end = self._buffer.get_end_iter()
        self._buffer.insert_with_tags_by_name(end, f"│ {block.content}", "blockquote")
    
    def _render_list(self, block: MarkdownBlock):
        for idx, item in enumerate(block.items):
            if block.block_type == BlockType.UNORDERED_LIST:
                bullet = "  •  "
            else:
                bullet = f"  {idx + 1}.  "
            
            end = self._buffer.get_end_iter()
            self._buffer.insert_with_tags_by_name(end, bullet, "list_bullet")
            
            item_spans = _parse_inline(item)
            self._render_spans(item_spans, "list_item")
            
            if idx < len(block.items) - 1:
                self._insert_newline()
    
    def _render_hr(self):
        end = self._buffer.get_end_iter()
        self._buffer.insert_with_tags_by_name(end, "─" * 40, "hr")


# ─── Standalone Test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    TEST_MARKDOWN = """# Arova Response

Hello! I'm **Arova**, your spatial AI environment.

## What I can do

I can help you with:

- **Code execution** and shell commands
- *Semantic* memory retrieval
- `inline code` formatting
- Deep reasoning tasks

### Example Code

```python
def hello():
    print("Hello from Arova!")
```

> "The best interface is absence."
> — Arova Design Philosophy

---

1. First, I analyze your workspace
2. Then, I build a [semantic model](https://arova.dev)
3. Finally, I act with restraint
"""

    app = Gtk.Application()
    
    def on_activate(app):
        win = Gtk.ApplicationWindow(application=app, title="Markdown Preview")
        win.set_default_size(600, 500)
        
        css = b"""
        window { background-color: #0f1218; }
        .md-textview { background-color: transparent; }
        textview text { background-color: transparent; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        
        md_view = MarkdownTextView()
        md_view.render(TEST_MARKDOWN)
        scroll.set_child(md_view)
        
        win.set_child(scroll)
        win.present()
    
    app.connect("activate", on_activate)
    app.run()
