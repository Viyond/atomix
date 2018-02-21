from logger import Logger
from errors import UnknownNetworkError
import docker

class Network(object):
    """Atomix test network."""
    def __init__(self, name):
        self.log = Logger(name, Logger.Type.FRAMEWORK)
        self.name = name
        self._docker_client = docker.from_env()

    @property
    def docker_network(self):
        try:
            return self._docker_client.networks.get(self.name)
        except docker.errors.NotFound:
            raise UnknownNetworkError(self.name)

    def setup(self, subnet, gateway):
        """Sets up the network."""
        ipam_pool = docker.types.IPAMPool(
            subnet=subnet,
            gateway=gateway
        )
        ipam_config = docker.types.IPAMConfig(
            pool_configs=[ipam_pool]
        )
        self.log.message("Creating network")
        self._docker_client.networks.create(self.name, driver='bridge', ipam=ipam_config)

    def teardown(self):
        """Tears down the network."""
        self.log.message("Removing network")
        self.docker_network.remove()

    def _percentize(self, d, digits=2):
        return round(d * 100, digits) + '%'

    def _millize(self, ms):
        return ms + 'ms'

    def partition(self, local, remote):
        """Partitions the given local from the given remote."""
        self.log.message("Cutting off link {}->{}", local.name, remote.name)
        local.run('/bin/bash', 'sudo', 'iptables', '-A', 'INPUT', '-s', remote.ip, '-j', 'DROP', '-w')

    def heal(self, local, remote):
        """Heals a partition from the given local to the given remote."""
        self.log.message("Restoring link {}->{}", local.name, remote.name)
        local.run('/bin/bash', 'sudo', 'iptables', '-D', 'INPUT', '-s', remote.ip, '-j', 'DROP', '-w')

    def isolate(self, node):
        """Isolates the given node from all its peers."""
        self.log.message("Isolating node {}", node.name)
        for n in node.cluster.nodes:
            if n.name != node.name:
                self.partition(node, n)
                self.partition(n, node)

    def unisolate(self, node):
        """Unisolates the given node from all its peers."""
        self.log.message("Healing node {}", node.name)
        for n in node.cluster.nodes:
            if n.name != node.name:
                self.heal(node, n)
                self.heal(n, node)

    def delay(self, node, latency=50, jitter=10, correlation=.75, distribution='normal'):
        """Delays packets to the given node."""
        correlation = self._percentize(correlation)
        self.log.message("Delaying packets to {} (latency={}, jitter={}, correlation={}, distribution={})", node.name, self._millize(latency), self._millize(jitter), correlation, distribution)
        node.run('/bin/bash', 'sudo', 'tc', 'qdisc', 'add', 'dev', 'eth0', 'root', 'netem', 'delay', latency, jitter, correlation, 'distribution', distribution)

    def drop(self, node, probability=.02, correlation=.25):
        """Drops packets to the given node."""
        probability, correlation = self._percentize(probability), self._percentize(correlation)
        self.log.message("Dropping packets to {} (probability={}, correlation={})", node.name, probability, correlation)
        node.run('/bin/bash', 'sudo', 'tc', 'qdisc', 'add', 'dev', 'eth0', 'root', 'netem', 'loss', probability, correlation)

    def reorder(self, node, probability=.02, correlation=.5):
        """Reorders packets to the given node."""
        probability, correlation = self._percentize(probability), self._percentize(correlation)
        self.log.message("Reordering packets to {} (probability={}, correlation={})", node.name, probability, correlation)
        node.run('/bin/bash', 'sudo', 'tc', 'qdisc', 'add', 'dev', 'eth0', 'root', 'netem', 'reorder', probability, correlation)

    def duplicate(self, node, probability=.005, correlation=.05):
        """Duplicates packets to the given node."""
        probability, correlation = self._percentize(probability), self._percentize(correlation)
        self.log.message("Duplicating packets to {} (probability={}, correlation={})", node.name, probability, correlation)
        node.run('/bin/bash', 'sudo', 'tc', 'qdisc', 'add', 'dev', 'eth0', 'root', 'netem', 'duplicate', probability, correlation)

    def corrupt(self, node, probability=.02):
        """Duplicates packets to the given node."""
        probability = self._percentize(probability)
        self.log.message("Corrupting packets to {} (probability={})", node.name, probability)
        node.run('/bin/bash', 'sudo', 'tc', 'qdisc', 'add', 'dev', 'eth0', 'root', 'netem', 'corrupt', probability)

    def restore(self, node):
        """Restores packets to the given node to normal order."""
        self.log.message("Restoring packets to {}", node.name)
        node.run('/bin/bash', 'sudo', 'tc', 'qdisc', 'del', 'dev', 'eth0', 'root')