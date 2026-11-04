# Project contents and provenance

This repository was assembled from the two project archives supplied for SENTINEL: the main Ubuntu project archive and the shared-folder archive containing the Flask backend and website.

Backup variants and Python bytecode caches were excluded. The active files retained are `controller/simple_switch.py`, `topology/topology_manager.py`, `backend/app.py`, the four website assets, and the TCP `server.py`/`client.py` pair.

The backend and controller data paths were made repository-relative in this assembled copy so that a clone does not depend on the original developer's `/home/.../cn_project/person1` directory. The original uploaded ZIP files were not modified.
