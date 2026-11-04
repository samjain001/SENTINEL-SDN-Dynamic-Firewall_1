 

import csv
import json
import os
import tempfile
from pathlib import Path
from datetime import datetime

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import (
    CONFIG_DISPATCHER,
    MAIN_DISPATCHER,
    DEAD_DISPATCHER,
    set_ev_cls
)
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib import hub
from os_ken.lib.packet import packet
from os_ken.lib.packet import ethernet
from os_ken.lib.packet import ether_types


BASE_DIR = Path(__file__).resolve().parent.parent

LOG_FILE = BASE_DIR / "traffic_log.csv"
OPENFLOW_STATS_FILE = BASE_DIR / "openflow_drop_stats.json"

SERVER_IP = "10.0.0.1"
SERVER_PORT = 5000


class SimpleSwitch13(app_manager.OSKenApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)

        self.mac_to_port = {}
        self.datapaths = {}

        self.last_row_count = self.get_csv_row_count()

        # Store multipart statistics replies.
        self.stats_parts = {}

        # Store the last collected statistics.
        self.drop_stats = {}

        self.logger.info("Sentinel SDN Controller initialized")

        self.logger.info("Monitoring security log: %s", LOG_FILE)

        # Monitor application-level security events.
        self.security_thread = hub.spawn(
            self.monitor_security_log
        )

        # Periodically request OpenFlow statistics.
        self.stats_thread = hub.spawn(
            self.monitor_openflow_stats
        )

    # --------------------------------------------------
    # SECURITY LOG MONITORING
    # --------------------------------------------------

    def get_csv_row_count(self):

        try:
            with open(LOG_FILE, "r", newline="") as file:
                return max(sum(1 for _ in csv.DictReader(file)), 0)

        except (FileNotFoundError, OSError):
            return 0

    def read_security_log(self):

        try:
            with open(LOG_FILE, "r", newline="") as file:
                return list(csv.DictReader(file))

        except (FileNotFoundError, OSError):
            return []

    def monitor_security_log(self):

        while True:

            try:
                rows = self.read_security_log()

                if len(rows) < self.last_row_count:
                    self.last_row_count = 0

                new_rows = rows[self.last_row_count:]

                for row in new_rows:

                    decision = row.get("Decision", "").strip().upper()

                    source_ip = (
                        row.get("Source IP")
                        or row.get("SourceIP")
                        or row.get("Source")
                        or ""
                    ).strip()

                    if decision == "BLOCKED" and source_ip:

                        self.logger.warning(
                            "New security event: BLOCKED traffic from %s",
                            source_ip
                        )

                        for datapath in list(self.datapaths.values()):
                            self.install_drop_rule(
                                datapath,
                                source_ip
                            )

                self.last_row_count = len(rows)

            except Exception as error:

                self.logger.error(
                    "Security monitoring error: %s",
                    error
                )

            hub.sleep(1)

    # --------------------------------------------------
    # OPENFLOW DROP RULE
    # --------------------------------------------------

    def add_flow(
        self,
        datapath,
        priority,
        match,
        actions,
        hard_timeout=0
    ):

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        instructions = []

        if actions:
            instructions = [
                parser.OFPInstructionActions(
                    ofproto.OFPIT_APPLY_ACTIONS,
                    actions
                )
            ]

        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions,
            hard_timeout=hard_timeout
        )

        datapath.send_msg(flow_mod)

    def install_drop_rule(self, datapath, source_ip):

        parser = datapath.ofproto_parser

        match = parser.OFPMatch(
            eth_type=0x0800,
            ipv4_src=source_ip,
            ipv4_dst=SERVER_IP,
            ip_proto=6,
            tcp_dst=SERVER_PORT
        )

        self.add_flow(
            datapath=datapath,
            priority=100,
            match=match,
            actions=[],
            hard_timeout=30
        )

        self.logger.warning(
            "OPENFLOW DROP RULE INSTALLED: %s -> %s:%s (expires in 30 seconds)",
            source_ip,
            SERVER_IP,
            SERVER_PORT
        )

    # --------------------------------------------------
    # SWITCH CONNECTION
    # --------------------------------------------------

    @set_ev_cls(
        ofp_event.EventOFPStateChange,
        [MAIN_DISPATCHER, DEAD_DISPATCHER]
    )
    def state_change_handler(self, event):

        datapath = event.datapath
        dpid = datapath.id

        if event.state == MAIN_DISPATCHER:

            self.datapaths[dpid] = datapath

            self.logger.info(
                "Switch %s connected to Sentinel controller",
                dpid
            )

        elif event.state == DEAD_DISPATCHER:

            self.datapaths.pop(dpid, None)
            self.stats_parts.pop(dpid, None)

            self.logger.warning(
                "Switch %s disconnected",
                dpid
            )

    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER
    )
    def switch_features_handler(self, event):

        datapath = event.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        self.datapaths[datapath.id] = datapath

        # Default table-miss rule.
        match = parser.OFPMatch()

        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]

        self.add_flow(
            datapath,
            0,
            match,
            actions
        )

        self.logger.info(
            "Switch %s connected using OpenFlow 1.3",
            datapath.id
        )

    # --------------------------------------------------
    # LEARNING SWITCH
    # --------------------------------------------------

    @set_ev_cls(
        ofp_event.EventOFPPacketIn,
        MAIN_DISPATCHER
    )
    def packet_in_handler(self, event):

        msg = event.msg
        datapath = msg.datapath

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)

        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None:
            return

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src

        dpid = datapath.id

        self.mac_to_port.setdefault(dpid, {})

        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:

            out_port = self.mac_to_port[dpid][dst]

        else:

            out_port = ofproto.OFPP_FLOOD

        actions = [
            parser.OFPActionOutput(out_port)
        ]

        if out_port != ofproto.OFPP_FLOOD:

            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst
            )

            self.add_flow(
                datapath,
                10,
                match,
                actions
            )

        data = None

        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )

        datapath.send_msg(out)

    # --------------------------------------------------
    # OPENFLOW STATISTICS MONITORING
    # --------------------------------------------------

    def monitor_openflow_stats(self):

        while True:

            try:

                for datapath in list(self.datapaths.values()):

                    parser = datapath.ofproto_parser

                    request = parser.OFPFlowStatsRequest(
                        datapath
                    )

                    self.stats_parts[datapath.id] = []

                    datapath.send_msg(request)

            except Exception as error:

                self.logger.error(
                    "Statistics request error: %s",
                    error
                )

            hub.sleep(2)

    @set_ev_cls(
        ofp_event.EventOFPFlowStatsReply,
        MAIN_DISPATCHER
    )
    def flow_stats_reply_handler(self, event):

        msg = event.msg
        datapath = msg.datapath
        dpid = datapath.id

        self.stats_parts.setdefault(dpid, [])

        self.stats_parts[dpid].extend(msg.body)

        ofproto = datapath.ofproto

        more_replies = (
            msg.flags & ofproto.OFPMPF_REPLY_MORE
        )

        if more_replies:
            return

        drop_flows = []

        total_packets = 0
        total_bytes = 0

        for flow in self.stats_parts[dpid]:

            # Our security drop rules use priority 100.
            if flow.priority != 100:
                continue

            # Drop rules have no output instructions.
            if flow.instructions:
                continue

            match = flow.match

            source_ip = match.get("ipv4_src")
            destination_ip = match.get("ipv4_dst")
            protocol = match.get("ip_proto")
            destination_port = match.get("tcp_dst")

            if (
                source_ip is None
                or destination_ip != SERVER_IP
                or protocol != 6
                or destination_port != SERVER_PORT
            ):
                continue

            packets = int(flow.packet_count)
            byte_count = int(flow.byte_count)

            total_packets += packets
            total_bytes += byte_count

            drop_flows.append({
                "source_ip": source_ip,
                "destination_ip": destination_ip,
                "destination_port": destination_port,
                "packets": packets,
                "bytes": byte_count,
                "duration_sec": int(flow.duration_sec)
            })

        self.drop_stats[str(dpid)] = {
            "total_dropped_packets": total_packets,
            "total_dropped_bytes": total_bytes,
            "flows": drop_flows
        }

        self.write_openflow_stats()

        self.stats_parts[dpid] = []

    # --------------------------------------------------
    # SAVE STATISTICS AS JSON
    # --------------------------------------------------

    def write_openflow_stats(self):

        try:

            all_flows = []

            total_packets = 0
            total_bytes = 0

            for switch_id, stats in self.drop_stats.items():

                total_packets += stats["total_dropped_packets"]
                total_bytes += stats["total_dropped_bytes"]

                for flow in stats["flows"]:

                    flow_data = dict(flow)
                    flow_data["switch_id"] = switch_id

                    all_flows.append(flow_data)

            output = {
                "updated_at": datetime.now().astimezone().isoformat(),
                "total_dropped_packets": total_packets,
                "total_dropped_bytes": total_bytes,
                "flows": all_flows
            }

            BASE_DIR.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=BASE_DIR,
                delete=False
            ) as temporary_file:

                json.dump(
                    output,
                    temporary_file,
                    indent=4
                )

                temporary_path = temporary_file.name

            os.replace(
                temporary_path,
                OPENFLOW_STATS_FILE
            )

        except Exception as error:

            self.logger.error(
                "Could not write OpenFlow statistics: %s",
                error
            )


