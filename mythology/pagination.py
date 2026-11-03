"""Pagination of the public collection.

Fixed size and page number: the simplest contract to document and to
consume. No size parameter is exposed, which prevents a client from
requesting a page of ten thousand records.
"""

from rest_framework.pagination import PageNumberPagination


class EntityPagination(PageNumberPagination):
    """Twenty records per page, a size the client cannot negotiate.

    The envelope is the DRF one - `count`, `next`, `previous`, `results` -
    and the standard behaviour is kept for a non-existent page, which
    returns 404.
    """

    page_size = 20
