# Administrative workflow coverage

| Existing Django capability | OMDA entry point | Execution and permissions |
|---|---|---|
| View hotels, search and inspect subscriptions | Hotels → hotel details | Existing staff workspace access; Django Admin listing also remains available. |
| Add/edit hotels | Hotels → Add Hotel / Edit | Existing model forms and add/change permissions. |
| Delete hotel, bulk delete, object history | Hotels → Delete / System Administration | Django Admin confirmation and delete permission, protected related records, native bulk actions and history. |
| List, search, filter and inspect licenses | Licenses → serial number | View permission, pagination, activation filter, search by serial, plan or hotel. |
| Add/edit license, change activation record and expiration | Licenses → Add / Edit | Existing model validation and add/change permissions. Editing activation updates the recorded flag only. |
| Record renewal | License Details → Record Renewal | Existing add-license form preselects the installation; creates a separate record. |
| Delete license, bulk delete, object history | License Details → Delete / System Administration | Existing Django Admin actions and permissions. |
| List, search, add and edit installations | Installations | Existing view/add/change permissions and fields. |
| Issue/rotate a sync token and request a sync | Installations → hotel detail → matching installation | Existing superuser-only actions. Django Admin also retains its token rotation action. |
| Delete installation, bulk delete, object history | Installations → Delete / System Administration | Existing Django Admin confirmation and protected relationships. |
| List, search, add, edit and delete users; change passwords; assign groups and user permissions; bulk delete and history | System Administration → Users | Existing Django Admin forms and permission checks. |
| List, search, add, edit and delete groups; assign permissions; bulk delete and history | System Administration → Groups | Existing Django Admin forms and permission checks. Permission assignment is exposed through users and groups; there is no separate permission-model registration. |
| Dashboard and sign-in/out | Workspace navigation | Existing Django sessions, staff gate and CSRF-protected sign-out. |

Subscription distribution counts the latest activated license per installation that has started. The database stores license records and an activation flag. It has no time-series snapshots or expiration events suitable for reconstructing historical subscription status.
