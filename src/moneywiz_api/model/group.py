from dataclasses import dataclass

from moneywiz_api.model.record import Record
from moneywiz_api.types import ID


@dataclass
class Group(Record):
    """
    ENT: 22
    """

    name: str
    user: ID
    group_id: int
    display_order: int

    def __init__(self, row):
        super().__init__(row)
        self.name = row["ZNAME4"]
        self.group_id = row["ZGROUPID3"]
        self.display_order = row["ZDISPLAYORDER4"]
        self.user = row["ZUSER5"]


        # Fixes

        # Validate
        assert self.name is not None, self.as_dict()
        assert self.user is not None, self.as_dict()
