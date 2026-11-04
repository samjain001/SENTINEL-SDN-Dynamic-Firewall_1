from mininet.topo import Topo


class Person1Topo(Topo):
    def build(self):
        # Create three virtual hosts
        h1 = self.addHost("h1", ip="10.0.0.1/24")
        h2 = self.addHost("h2", ip="10.0.0.2/24")
        h3 = self.addHost("h3", ip="10.0.0.3/24")

        # Create one Open vSwitch switch
        s1 = self.addSwitch("s1")

        # Connect all hosts to the switch
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)


topos = {
    "person1topo": lambda: Person1Topo()
}
