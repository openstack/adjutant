from rest_framework.views import APIView
from rest_framework.response import Response


_VERSIONS = {}


def build_version_details(id, status, links=None, relative_endpoint=None):
    """
    Build a standard version dictionary
    """
    int_id = int(float(id))
    if not relative_endpoint:
        relative_endpoint = "v%s/" % int_id
    mime_type = "application/vnd.openstack.adjutant-v%s+json" % int_id
    version_details = {
        "status": status,
        "id": id,
        "media-types": [{"base": "application/json", "type": mime_type}],
        "links": [],
    }

    if links:
        version_details["links"] = links

    version_details["relative_endpoint"] = relative_endpoint
    _VERSIONS[id] = version_details
    return version_details


class VersionView(APIView):
    def get(self, request):
        versions = []
        for version in _VERSIONS.values():
            version = version.copy()
            rel_endpoint = version.pop("relative_endpoint")
            url = request.build_absolute_uri() + rel_endpoint
            version["links"] = version["links"] + [{"href": url, "rel": "self"}]
            versions.append(version)

        return Response({"versions": versions}, status=200)


class SingleVersionView(APIView):
    """
    A view to be added to the root of each API version detailing it's
    own version details. Should be subclassed and have a version set.
    """

    def get(self, request):

        version = _VERSIONS.get(self.version, {}).copy()
        if not version:
            return Response({"error": "Not Found"}, status=404)

        version.pop("relative_endpoint")

        version["links"] = version["links"] + [
            {"href": request.build_absolute_uri(), "rel": "self"}
        ]
        return Response({"version": version}, status=200)
