from abc import ABC, abstractmethod
from recon.models import NormalizedRecord

class BaseSource(ABC):
    """Abstract base for all data source loaders."""
    
    @abstractmethod
    def load(self) -> list[NormalizedRecord]:
        """Load and normalize records from this source."""
        ...
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name of this source."""
        ...
