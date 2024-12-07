from typing import Dict, Callable

from moneywiz_api.model.group import Group
from moneywiz_api.managers.record_manager import RecordManager


class GroupManager(RecordManager[Group]):
    def __init__(self):
        super().__init__()

    @property
    def ents(self) -> Dict[str, Callable]:
        return {
            "Group": Group,
        }

    def get_group_by_group_id(self, group_id: int) -> Group:
        return next((x for _, x in self.records().items() if x.group_id == group_id), None)
