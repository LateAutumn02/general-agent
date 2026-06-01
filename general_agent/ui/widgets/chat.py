"""Chat container with text-selectable Rich renderables.

Reference: TunaCode widgets/chat.py (SelectableRichVisual, CopyOnSelectStatic)
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice

from rich.console import RenderableType
from rich.segment import Segment
from rich.style import Style as RichStyle
from textual._context import active_app
from textual.containers import VerticalScroll
from textual.css.styles import RulesMap
from textual.geometry import Region, Size
from textual.selection import Selection
from textual.strip import Strip
from textual.style import Style
from textual.visual import RichVisual, Visual, visualize
from textual.widget import Widget
from textual.widgets import Static


# -- Panel metadata -----------------------------------------------


@dataclass(frozen=True)
class PanelMeta:
    """Optional styling metadata for a message widget.

    ``ChatContainer.write()`` applies these as CSS classes and border
    labels so renderers don't need Rich ``Panel()`` wrappers.
    """

    css_class: str = ""
    border_title: str = ""
    border_subtitle: str = ""


# -- SelectableRichVisual -----------------------------------------


class SelectableRichVisual(RichVisual):
    """RichVisual that injects offset metadata so Textual's mouse
    text-selection works on Rich renderables."""

    def render_strips(
        self,
        _rules: RulesMap,
        width: int,
        height: int | None,
        style: Style,
        selection: Selection | None = None,
        selection_style: Style | None = None,
        _post_style: Style | None = None,
    ) -> list[Strip]:
        app = active_app.get()
        console = app.console
        options = console.options.update(highlight=False, width=width, height=height)
        renderable = self._widget.post_render(self._renderable, style.rich_style)
        segments = console.render(renderable, options.update_width(width))
        raw_lines = Segment.split_and_crop_lines(segments, width, include_new_lines=False, pad=False)

        get_span = selection.get_span if selection is not None else None
        sel_style = selection_style.rich_style if selection_style is not None else None

        def with_offset(s: RichStyle | None, x: int, y: int) -> RichStyle:
            base = s or RichStyle.null()
            return base + RichStyle(meta={"offset": (x, y)})

        strips: list[Strip] = []
        for y, line in enumerate(islice(raw_lines, None, height)):
            span = get_span(y) if get_span is not None else None
            x = 0
            new_segments: list[Segment] = []
            for segment in line:
                if segment.control:
                    new_segments.append(segment)
                    continue
                seg_cells = segment.cell_length
                if span is None or sel_style is None:
                    new_segments.append(Segment(segment.text, with_offset(segment.style, x, y)))
                    x += seg_cells
                    continue
                start, end = span
                end_ex = x + seg_cells if end == -1 else end + 1
                overlap_start = max(x, start)
                overlap_end = min(x + seg_cells, end_ex)
                if overlap_start >= overlap_end:
                    new_segments.append(Segment(segment.text, with_offset(segment.style, x, y)))
                    x += seg_cells
                    continue
                pre_cut = overlap_start - x
                post_cut = overlap_end - x
                left, remainder = segment.split_cells(pre_cut)
                middle, right = remainder.split_cells(post_cut - pre_cut)
                if left.text:
                    new_segments.append(Segment(left.text, with_offset(segment.style, x, y)))
                if middle.text:
                    new_segments.append(
                        Segment(middle.text, with_offset(segment.style, x + pre_cut, y) + sel_style)
                    )
                if right.text:
                    new_segments.append(
                        Segment(right.text, with_offset(segment.style, x + post_cut, y))
                    )
                x += seg_cells
            strips.append(Strip(new_segments))
        return strips


# -- CopyOnSelectStatic -------------------------------------------


class CopyOnSelectStatic(Static):
    """Static widget that supports mouse-selection for Rich renderables."""

    def _render(self) -> Visual:
        cache_key = "_render.visual"
        cached = self._layout_cache.get(cache_key, None)
        if cached is not None:
            return cached
        visual = visualize(self, self.render(), markup=self._render_markup)
        if isinstance(visual, RichVisual) and not isinstance(visual, SelectableRichVisual):
            visual = SelectableRichVisual(self, visual._renderable)
        self._layout_cache[cache_key] = visual
        return visual

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        visual = self._render()
        if isinstance(visual, SelectableRichVisual):
            width = self.size.width
            strips = Visual.to_strips(self, visual, width, None, self.visual_style, pad=False)
            text = "\n".join(strip.text for strip in strips)
            return selection.extract(text), "\n"
        return super().get_selection(selection)


# -- ChatContainer ------------------------------------------------


class ChatContainer(VerticalScroll):
    """Scrollable message history.  Each ``write()`` mounts a
    ``CopyOnSelectStatic`` child so mouse-selection works."""

    DEFAULT_CSS = """
    ChatContainer {
        height: 1fr;
        scrollbar-gutter: stable;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)

    def write(
        self,
        renderable: RenderableType,
        *,
        expand: bool = False,
        panel_meta: PanelMeta | None = None,
    ) -> CopyOnSelectStatic:
        """Append a Rich renderable as a new chat message.

        Args:
            renderable: Rich ``Text`` / ``Panel`` / ``Markdown`` etc.
            expand:     If True, widget expands to fill available width.
            panel_meta: Optional border title / CSS classes.

        Returns:
            The mounted ``CopyOnSelectStatic`` widget.
        """
        widget = CopyOnSelectStatic(renderable)
        widget.add_class("chat-message")

        if expand:
            widget.add_class("expand")

        if panel_meta is not None:
            if panel_meta.css_class:
                for cls in panel_meta.css_class.split():
                    widget.add_class(cls)
            if panel_meta.border_title:
                widget.border_title = panel_meta.border_title
            if panel_meta.border_subtitle:
                widget.border_subtitle = panel_meta.border_subtitle

        self.mount(widget)
        self.scroll_end(animate=False)
        return widget

    def clear(self) -> None:
        """Remove all messages from the container."""
        for child in list(self.children):
            child.remove()

    @property
    def content_region(self) -> Region:
        return self.scrollable_content_region

    @property
    def size(self) -> Size:
        return super().size
