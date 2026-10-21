"""Pagination de la collection publique.

Taille fixe et numéro de page : le contrat le plus simple à documenter et à
consommer. Aucun paramètre de taille n'est exposé, ce qui évite qu'un client
demande une page de dix mille fiches.
"""

from rest_framework.pagination import PageNumberPagination


class EntityPagination(PageNumberPagination):
    """Vingt fiches par page, taille non négociable par le client.

    L'enveloppe est celle de DRF — `count`, `next`, `previous`, `results` —
    et le comportement standard est conservé pour une page inexistante, qui
    renvoie 404.
    """

    page_size = 20
