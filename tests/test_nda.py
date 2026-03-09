from artsecure_bot.services.nda import build_nda_pdf


def test_build_nda_pdf_starts_with_pdf_signature() -> None:
    pdf_bytes = build_nda_pdf(
        order_id=101,
        customer_name="Alice",
        artist_name="Bob",
        work_title="Portrait",
        price_rub=15000,
    )

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000
