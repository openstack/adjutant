from rest_framework import serializers


class NewNetworkSerializer(serializers.Serializer):
    network_name = serializers.CharField(max_length=200)


class NewRouterSerializer(serializers.Serializer):
    router_name = serializers.CharField(max_length=200)
