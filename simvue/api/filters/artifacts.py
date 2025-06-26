"""Defines filters for Artifact retrieval."""

from .base import RestAPIFilter, ObjectStrProperty, PropertyComposite, MetadataFilter


class ArtifactsFilter(RestAPIFilter):
    """Filter for browsing Artifact objects."""

    @property
    def name(self) -> ObjectStrProperty:
        """Return comparator for Artifact name."""
        return ObjectStrProperty("name", self)

    @property
    def metadata(self) -> PropertyComposite:
        """Return comparator for Artifact metadata."""
        return MetadataFilter(self)
