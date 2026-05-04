import pytest
import jwt

from xoloapi.licenses.dto import AssignLicenseDTO, DeleteLicenseDTO, SelfDeleteLicenseDTO

ACCOUNT_ID = "acc-test"


@pytest.mark.asyncio
async def test_licenses_service_assign_and_prevent_duplicate(licenses_service):
    first = await licenses_service.assign_license(
        ACCOUNT_ID,
        AssignLicenseDTO(username="alice", scope="ops", expires_in="15m", force=True)
    )
    assert first.is_ok

    second = await licenses_service.assign_license(
        ACCOUNT_ID,
        AssignLicenseDTO(username="alice", scope="ops", expires_in="15m", force=False)
    )
    assert second.is_err


@pytest.mark.asyncio
async def test_licenses_service_self_delete(licenses_service):
    await licenses_service.assign_license(
        ACCOUNT_ID,
        AssignLicenseDTO(username="alice", scope="ops", expires_in="15m", force=True)
    )
    tmp_secret = "temporary-secret"
    token = jwt.encode({"iss": "OPS", "uid2": "alice"}, tmp_secret, algorithm="HS256")

    deleted = await licenses_service.self_delete_license(
        ACCOUNT_ID,
        SelfDeleteLicenseDTO(
            token=token,
            tmp_secret_key=tmp_secret,
            username="alice",
            scope="ops",
        )
    )
    assert deleted.is_ok
    assert deleted.unwrap().ok is True


@pytest.mark.asyncio
async def test_licenses_service_delete(licenses_service):
    await licenses_service.assign_license(
        ACCOUNT_ID,
        AssignLicenseDTO(username="alice", scope="ops", expires_in="15m", force=True)
    )
    deleted = await licenses_service.delete_license(ACCOUNT_ID, DeleteLicenseDTO(username="alice", scope="ops"))
    assert deleted.is_ok


@pytest.mark.asyncio
async def test_licenses_service_list(licenses_service):
    await licenses_service.assign_license(
        ACCOUNT_ID,
        AssignLicenseDTO(username="alice", scope="ops", expires_in="15m", force=True)
    )
    listed = await licenses_service.list_licenses(ACCOUNT_ID)
    assert listed.is_ok
    assert len(listed.unwrap()) == 1
    assert listed.unwrap()[0].scope == "OPS"
