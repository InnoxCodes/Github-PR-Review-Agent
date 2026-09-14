from fastapi import APIRouter, Response

from app.api.deps import ServicesDep
from app.demo.seed import clear_sample_data, load_sample_data
from app.schemas import SampleDataResult

router = APIRouter(prefix="/api/demo", tags=["system"])


@router.post("/sample-data", response_model=SampleDataResult, summary="Load labelled sample reviews")
async def load_samples(services: ServicesDep) -> SampleDataResult:
    """Loads ten sample reviews across three fictional repositories (owner `reviewmind-demo`)
    so the dashboard can be explored without an LLM API key. Sample findings are hand-written,
    not model output, and every sample review is flagged `is_sample`. Calling it again
    replaces the previous sample set; real reviews are never touched."""
    reviews, repositories = await load_sample_data(services.session_factory, services.settings)
    return SampleDataResult(reviews=reviews, repositories=repositories)


@router.delete("/sample-data", status_code=204, summary="Remove all sample reviews")
async def clear_samples(services: ServicesDep) -> Response:
    await clear_sample_data(services.session_factory)
    return Response(status_code=204)
