from xoloapi.ngac.domain.aggregates import NGACAssignment as DomainNGACAssignment
from xoloapi.ngac.domain.aggregates import NGACAssociation as DomainNGACAssociation
from xoloapi.ngac.domain.aggregates import NGACNode as DomainNGACNode


class _CompatMixin:
    def __getitem__(self, key: str):
        return getattr(self, key)


class NGACNode(_CompatMixin, DomainNGACNode):
    pass


class NGACAssignment(_CompatMixin, DomainNGACAssignment):
    pass


class NGACAssociation(_CompatMixin, DomainNGACAssociation):
    pass


__all__ = ["NGACNode", "NGACAssignment", "NGACAssociation"]
