"""Court Document Assembly data models."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    INDICTMENT = "indictment"
    EVIDENCE_SUMMARY = "evidence_summary"
    WITNESS_LIST = "witness_list"
    EXHIBIT_LIST = "exhibit_list"
    SENTENCING_MEMORANDUM = "sentencing_memorandum"
    CASE_BRIEF = "case_brief"
    MOTION_IN_LIMINE = "motion_in_limine"
    MOTION_TO_COMPEL = "motion_to_compel"
    RESPONSE_TO_MOTION = "response_to_motion"
    NOTICE_OF_EVIDENCE = "notice_of_evidence"
    PLEA_AGREEMENT = "plea_agreement"


class DocumentStatus(str, Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    FINAL = "final"
    ARCHIVED = "archived"


class PrivilegeCategory(str, Enum):
    NON_PRIVILEGED = "non_privileged"
    ATTORNEY_CLIENT = "attorney_client"
    WORK_PRODUCT = "work_product"
    BRADY_MATERIAL = "brady_material"
    JENCKS_MATERIAL = "jencks_material"
    PENDING = "pending"


class ProductionStatus(str, Enum):
    PENDING = "pending"
    PRODUCED = "produced"
    WITHHELD = "withheld"


class WitnessRole(str, Enum):
    VICTIM = "victim"
    FACT_WITNESS = "fact_witness"
    EXPERT_WITNESS = "expert_witness"
    COOPERATING_WITNESS = "cooperating_witness"
    LAW_ENFORCEMENT = "law_enforcement"


class ExhibitType(str, Enum):
    DOCUMENTARY = "documentary"
    PHYSICAL = "physical"
    DIGITAL = "digital"
    TESTIMONIAL = "testimonial"


class DocumentSection(BaseModel):
    section_id: str
    draft_id: str
    section_type: str
    section_order: int
    content: str = ""
    decision_id: Optional[str] = None
    decision_state: Optional[str] = None


class DocumentDraft(BaseModel):
    draft_id: str
    case_id: str
    document_type: DocumentType
    title: str
    status: DocumentStatus = DocumentStatus.DRAFT
    statute_id: Optional[str] = None
    defendant_id: Optional[str] = None
    is_work_product: bool = False
    sections: list[DocumentSection] = []
    attorney_id: Optional[str] = None
    attorney_name: Optional[str] = None
    sign_off_at: Optional[str] = None
    created_at: str = ""
    updated_at: Optional[str] = None


class DocumentVersion(BaseModel):
    version_id: str
    draft_id: str
    version_number: int
    content_snapshot: dict = {}
    changed_sections: list[str] = []
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    created_at: str = ""


class VersionDiff(BaseModel):
    version_a: int
    version_b: int
    added_sections: list[str] = []
    removed_sections: list[str] = []
    modified_sections: list[dict] = []


class WitnessEntry(BaseModel):
    entity_name: str
    role: WitnessRole
    testimony_summary: str = ""
    credibility_assessment: str = ""
    impeachment_flags: list[str] = []
    document_count: int = 0
    co_occurrence_count: int = 0


class ExhibitEntry(BaseModel):
    exhibit_number: int
    document_id: str
    description: str = ""
    exhibit_type: ExhibitType = ExhibitType.DOCUMENTARY
    source: str = ""
    relevance: str = ""
    authentication_notes: str = ""
    linked_elements: list[str] = []


class GuidelineCalculation(BaseModel):
    statute_citation: str
    base_offense_level: int = Field(ge=1, le=43)
    adjustments: list[dict] = []
    total_offense_level: int = Field(ge=1, le=43)
    criminal_history_category: int = Field(ge=1, le=6)
    guideline_range_months_low: int = Field(ge=0)
    guideline_range_months_high: int = Field(ge=0)


class DiscoveryDocument(BaseModel):
    id: str
    case_id: str
    document_id: str
    privilege_category: PrivilegeCategory = PrivilegeCategory.PENDING
    production_status: ProductionStatus = ProductionStatus.PENDING
    privilege_description: str = ""
    privilege_doctrine: str = ""
    linked_witness_id: Optional[str] = None
    disclosure_alert: bool = False
    disclosure_alert_at: Optional[str] = None
    waiver_flag: bool = False
    decision_id: Optional[str] = None


class ProductionSet(BaseModel):
    production_id: str
    case_id: str
    production_number: int
    recipient: str
    document_ids: list[str] = []
    document_count: int = 0
    production_date: str = ""
    notes: str = ""


class DiscoveryStatus(BaseModel):
    total_documents: int = 0
    by_privilege: dict = {}
    by_production_status: dict = {}
    brady_alerts: int = 0
    waiver_flags: int = 0


class PrivilegeLogEntry(BaseModel):
    document_id: str
    privilege_category: str
    privilege_description: str = ""
    privilege_doctrine: str = ""
    date_withheld: str = ""
