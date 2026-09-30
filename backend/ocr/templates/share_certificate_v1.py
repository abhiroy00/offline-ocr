"""Document template for the classic Indian share-certificate layout used
by the sample corpus (Kamani Metals & Alloys and similar). Coordinates are
normalized (0-1, relative to page width/height) so the same template works
across scans of different resolution/DPI.

Regions are a *secondary* signal here: the primary extraction strategy is
keyword-anchored regex over the OCR'd text (see extraction_service.py),
which tolerates the layout drift common across decades of certificates far
better than fixed cropping would. A line whose bounding box falls inside
its field's expected region gets a small confidence boost; nothing is
extracted purely because it happened to fall inside a box.

Future certificate layouts can be added as sibling template modules and
selected by document_classifier without touching extraction_service.
"""

TEMPLATE_NAME = "share_certificate_v1"

# (x1, y1, x2, y2), normalized to page width/height.
PAGE_1_REGIONS = {
    "certificate_number": (0.0, 0.0, 0.20, 0.07),
    "number_of_shares_box": (0.80, 0.0, 1.0, 0.07),
    "company_name": (0.08, 0.10, 0.92, 0.26),
    "registered_office": (0.10, 0.26, 0.90, 0.31),
    "authorised_capital": (0.08, 0.31, 0.92, 0.35),
    "holder_name": (0.10, 0.44, 0.80, 0.53),
    "shares_and_face_value": (0.08, 0.53, 0.95, 0.64),
    "issue_date": (0.08, 0.63, 0.75, 0.71),
    "distinctive_numbers": (0.05, 0.735, 0.45, 0.80),
    "signatures": (0.50, 0.71, 0.98, 0.92),
}

PAGE_2_REGIONS = {
    "transfer_table": (0.0, 0.05, 1.0, 1.0),
    "transfer_table_header": (0.0, 0.05, 1.0, 0.10),
    "column_date": (0.0, 0.0, 0.13, 1.0),
    "column_transfer_no": (0.13, 0.0, 0.25, 1.0),
    "column_transferee": (0.25, 0.0, 0.66, 1.0),
    "column_ledger_folio": (0.66, 0.0, 0.80, 1.0),
    "column_signature": (0.80, 0.0, 1.0, 1.0),
}

TRANSFER_TABLE_COLUMNS = [
    "transfer_date",
    "transfer_no",
    "transferee_name",
    "ledger_folio_no",
    "authorised_signature",
]


def region_for(page: int, field: str):
    regions = PAGE_1_REGIONS if page == 1 else PAGE_2_REGIONS
    return regions.get(field)


def box_in_region(box: tuple, image_width: int, image_height: int, region: tuple, tolerance: float = 0.05) -> bool:
    """True if an absolute-pixel OCR line box's center falls within a
    normalized region (expanded slightly by `tolerance` to absorb noisy
    OCR bounding boxes near an edge)."""
    if not region:
        return False
    x1, y1, x2, y2 = region
    cx = ((box[0] + box[2]) / 2) / image_width
    cy = ((box[1] + box[3]) / 2) / image_height
    return (x1 - tolerance) <= cx <= (x2 + tolerance) and (y1 - tolerance) <= cy <= (y2 + tolerance)
