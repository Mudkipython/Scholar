from .models import SourceMetric


class ClarivateClient:
    """Placeholder for official JCR/JIF integration when API access is available."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def metric_for_issn_l(self, issn_l: str) -> SourceMetric:
        raise NotImplementedError(
            "Clarivate Web of Science Journals API integration requires an institutional API key and endpoint details."
        )
