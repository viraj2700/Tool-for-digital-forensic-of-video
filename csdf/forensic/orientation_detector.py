def detect_rotation_from_metadata(meta):
    """
    Look for rotate tags in streams' tags or side_data_list; return rotation in degrees.
    """
    if not meta:
        return "Unknown"
    streams = meta.get("streams", [])
    for s in streams:
        tags = s.get("tags", {}) or {}
        if "rotate" in tags:
            try:
                return f"{int(tags['rotate'])}°"
            except Exception:
                return tags['rotate']
        # side_data_list may contain rotation
        for sd in s.get("side_data_list", []) or []:
            if sd.get("rotation") is not None:
                return f"{int(sd.get('rotation'))}°"
    return "0°"
