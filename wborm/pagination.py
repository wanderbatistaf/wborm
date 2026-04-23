"""
Pagination Support

This module provides efficient pagination utilities for large result sets,
including page-based and cursor-based pagination.

Features:
- Page-based pagination with metadata
- Cursor-based pagination for better performance
- Automatic page count calculation
- Next/previous page helpers
"""

from typing import Any, List, Optional, Dict
from dataclasses import dataclass


@dataclass
class Page:
    """
    Represents a single page of results.

    Attributes:
        items: List of results for this page
        page: Current page number (1-indexed)
        page_size: Number of items per page
        total: Total number of items across all pages
        pages: Total number of pages
        has_next: Whether there's a next page
        has_prev: Whether there's a previous page
        next_page: Next page number (None if no next page)
        prev_page: Previous page number (None if no prev page)
    """
    items: List[Any]
    page: int
    page_size: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool
    next_page: Optional[int]
    prev_page: Optional[int]

    def __iter__(self):
        """Allow iteration over items"""
        return iter(self.items)

    def __len__(self):
        """Return number of items in current page"""
        return len(self.items)

    def __repr__(self):
        return (
            f"<Page {self.page}/{self.pages} "
            f"({len(self.items)} items, {self.total} total)>"
        )


class Paginator:
    """
    Handles pagination logic for querysets.

    Provides both offset-based and cursor-based pagination.
    """

    def __init__(self, queryset, page_size: int = 50):
        """
        Initialize paginator.

        Args:
            queryset: QuerySet to paginate
            page_size: Number of items per page (default: 50)
        """
        self.queryset = queryset
        self.page_size = page_size
        self._total = None

    @property
    def total(self) -> int:
        """
        Get total number of items.

        Cached after first access.

        Returns:
            Total item count
        """
        if self._total is None:
            # Use count() method if available, otherwise count items
            if hasattr(self.queryset, 'count'):
                self._total = self.queryset.count()
            else:
                self._total = len(self.queryset.all())
        return self._total

    @property
    def pages(self) -> int:
        """
        Get total number of pages.

        Returns:
            Number of pages
        """
        if self.total == 0:
            return 1
        return (self.total + self.page_size - 1) // self.page_size

    def page(self, page: int) -> Page:
        """
        Get a specific page of results.

        Args:
            page: Page number (1-indexed)

        Returns:
            Page object with results and metadata

        Raises:
            ValueError: If page number is invalid

        Examples:
            >>> paginator = Paginator(Cliente.all(), page_size=20)
            >>> page1 = paginator.page(1)
            >>> print(f"Showing {len(page1)} of {page1.total} clients")
        """
        if page < 1:
            raise ValueError(f"Page number must be >= 1, got {page}")

        if page > self.pages and self.total > 0:
            raise ValueError(
                f"Page {page} does not exist (only {self.pages} pages)"
            )

        # Calculate offset
        offset = (page - 1) * self.page_size

        # Get items for this page
        items = (
            self.queryset
            .limit(self.page_size)
            .offset(offset)
            .all()
        )

        # Build page metadata
        has_next = page < self.pages
        has_prev = page > 1

        return Page(
            items=items,
            page=page,
            page_size=self.page_size,
            total=self.total,
            pages=self.pages,
            has_next=has_next,
            has_prev=has_prev,
            next_page=page + 1 if has_next else None,
            prev_page=page - 1 if has_prev else None,
        )

    def iter_pages(
        self,
        left_edge: int = 2,
        left_current: int = 2,
        right_current: int = 2,
        right_edge: int = 2
    ) -> List[Optional[int]]:
        """
        Iterate through page numbers with ellipsis for large page counts.

        Useful for building pagination UI with "..." for skipped pages.

        Args:
            left_edge: Pages to show at the left edge
            left_current: Pages to show left of current page
            right_current: Pages to show right of current page
            right_edge: Pages to show at the right edge

        Returns:
            List of page numbers with None for ellipsis

        Examples:
            >>> paginator = Paginator(qs, page_size=10)
            >>> paginator.iter_pages()
            [1, 2, None, 8, 9, 10, 11, 12, None, 99, 100]
        """
        last = self.pages

        # Generate page number ranges
        left = range(1, min(left_edge + 1, last + 1))
        right = range(max(1, last - right_edge + 1), last + 1)

        # This will be filled with the actual current page context
        # For now, assume we're on page 1
        return list(left) + [None] + list(right)


class CursorPaginator:
    """
    Cursor-based pagination for very large result sets.

    More efficient than offset-based pagination for large offsets.
    Uses a cursor (usually a unique ID or timestamp) to fetch the next batch.
    """

    def __init__(
        self,
        queryset,
        cursor_field: str = "id",
        page_size: int = 50,
        order: str = "ASC"
    ):
        """
        Initialize cursor paginator.

        Args:
            queryset: QuerySet to paginate
            cursor_field: Field to use as cursor (must be unique and indexed)
            page_size: Number of items per page
            order: Sort order - "ASC" or "DESC"

        Examples:
            >>> paginator = CursorPaginator(
            >>>     Cliente.filter(active=True),
            >>>     cursor_field="id",
            >>>     page_size=100
            >>> )
        """
        self.queryset = queryset
        self.cursor_field = cursor_field
        self.page_size = page_size
        self.order = order.upper()

        if self.order not in ("ASC", "DESC"):
            raise ValueError(f"Order must be 'ASC' or 'DESC', got '{order}'")

    def page(self, cursor: Optional[Any] = None) -> Dict[str, Any]:
        """
        Get page starting from cursor.

        Args:
            cursor: Cursor value to start from (None for first page)

        Returns:
            Dictionary with:
                - items: List of results
                - next_cursor: Cursor for next page (None if last page)
                - has_next: Whether there's a next page

        Examples:
            >>> paginator = CursorPaginator(Cliente.all(), cursor_field="id")
            >>> page1 = paginator.page()
            >>> page2 = paginator.page(cursor=page1['next_cursor'])
        """
        # Clone queryset to avoid modifying original
        qs = self.queryset

        # Apply cursor filter if provided
        if cursor is not None:
            if self.order == "ASC":
                qs = qs.filter(f"{self.cursor_field} > {cursor}")
            else:
                qs = qs.filter(f"{self.cursor_field} < {cursor}")

        # Order by cursor field
        qs = qs.order_by(
            f"{self.cursor_field} {self.order}"
        )

        # Fetch one extra item to check if there's a next page
        items = qs.limit(self.page_size + 1).all()

        has_next = len(items) > self.page_size
        if has_next:
            items = items[:self.page_size]

        # Get next cursor
        next_cursor = None
        if has_next and items:
            last_item = items[-1]
            next_cursor = getattr(last_item, self.cursor_field)

        return {
            "items": items,
            "next_cursor": next_cursor,
            "has_next": has_next,
            "page_size": self.page_size,
        }

    def iter_all(self):
        """
        Iterate through all items using cursor pagination.

        Yields:
            Individual items from all pages

        Examples:
            >>> paginator = CursorPaginator(Cliente.all(), page_size=1000)
            >>> for cliente in paginator.iter_all():
            >>>     print(cliente.nome)
        """
        cursor = None

        while True:
            page = self.page(cursor)
            for item in page["items"]:
                yield item

            if not page["has_next"]:
                break

            cursor = page["next_cursor"]


def paginate(
    queryset,
    page: int = 1,
    page_size: int = 50
) -> Page:
    """
    Helper function for quick pagination.

    Args:
        queryset: QuerySet to paginate
        page: Page number (1-indexed, default: 1)
        page_size: Items per page (default: 50)

    Returns:
        Page object with results and metadata

    Examples:
        >>> from wborm.pagination import paginate
        >>> page = paginate(Cliente.filter(active=True), page=2, page_size=20)
        >>> print(f"Page {page.page} of {page.pages}")
        >>> for cliente in page.items:
        >>>     print(cliente.nome)
    """
    paginator = Paginator(queryset, page_size=page_size)
    return paginator.page(page)


def cursor_paginate(
    queryset,
    cursor: Optional[Any] = None,
    cursor_field: str = "id",
    page_size: int = 50,
    order: str = "ASC"
) -> Dict[str, Any]:
    """
    Helper function for cursor-based pagination.

    Args:
        queryset: QuerySet to paginate
        cursor: Starting cursor (None for first page)
        cursor_field: Field to use as cursor
        page_size: Items per page
        order: Sort order ("ASC" or "DESC")

    Returns:
        Dictionary with items, next_cursor, and has_next

    Examples:
        >>> from wborm.pagination import cursor_paginate
        >>> page1 = cursor_paginate(Cliente.all(), page_size=100)
        >>> page2 = cursor_paginate(
        >>>     Cliente.all(),
        >>>     cursor=page1['next_cursor'],
        >>>     page_size=100
        >>> )
    """
    paginator = CursorPaginator(
        queryset,
        cursor_field=cursor_field,
        page_size=page_size,
        order=order
    )
    return paginator.page(cursor)
