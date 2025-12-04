#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/error-model.h"
#include "ns3/queue.h"
#include "ns3/point-to-point-net-device.h"
#include "ns3/ipv4-static-routing-helper.h"

#include <fstream>
#include <sstream>
#include <vector>
#include <map>
#include <queue>
#include <limits>
#include <iostream>
#include <iomanip>
#include <algorithm>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("StarlinkSim");

// ==================== 数据结构 ====================

struct LinkParam {
    uint32_t srcId;
    uint32_t dstId;
    std::string srcName;
    std::string dstName;
    double delayMs;
    uint64_t dataRateBps;
    double packetLossRate;
    double distanceKm;
};

struct TrafficDemand {
    uint32_t demandId;
    std::string srcNode;
    std::string dstNode;
    uint32_t srcId;
    uint32_t dstId;
    double dataRateMbps;
    double startTimeSec;
    double durationSec;
};

struct LinkStats {
    std::string srcName;
    std::string dstName;
    uint64_t txPackets = 0;
    uint64_t rxPackets = 0;
};

struct MonitorEntry {
    std::string srcName;
    std::string dstName;
    Ptr<PointToPointNetDevice> device;
};

// ==================== 全局变量 ====================
std::vector<LinkStats> g_linkStats;
std::vector<LinkParam> g_links;
std::vector<TrafficDemand> g_demands;
std::vector<MonitorEntry> g_monitoredLinks;
uint32_t g_numNodes = 0;
NodeContainer g_nodes;

std::map<std::string, std::string> g_ipToSatellite;
std::map<uint32_t, std::string> g_nodeIdToName;
std::map<uint32_t, Ipv4Address> g_nodeFirstIp;
std::vector<std::vector<std::pair<uint32_t, double>>> g_adjList;

// 用于查找两个节点之间的接口信息
std::map<std::pair<uint32_t, uint32_t>, std::pair<uint32_t, Ipv4Address>> g_linkInterface;

std::ofstream g_monitorFile;

// ==================== 工具函数 ====================

std::string Trim(const std::string& s) {
    size_t start = s.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    size_t end = s.find_last_not_of(" \t\r\n");
    return s.substr(start, end - start + 1);
}

void MonitorQueues(double interval) {
    double now = Simulator::Now().GetSeconds();
    
    for (const auto& entry : g_monitoredLinks) {
        if (!entry.device) continue;
        
        Ptr<Queue<Packet>> queue = entry.device->GetQueue();
        uint32_t qSize = 0;
        if (queue) {
            qSize = queue->GetNPackets();
        }
        
        g_monitorFile << now << ","
                      << entry.srcName << ","
                      << entry.dstName << ","
                      << qSize << "\n";
    }
    g_monitorFile.flush();
    
    Simulator::Schedule(Seconds(interval), &MonitorQueues, interval);
}

static void LinkTxCallback(uint32_t linkIndex, Ptr<const Packet> p) {
    if (linkIndex < g_linkStats.size()) g_linkStats[linkIndex].txPackets++;
}
static void LinkRxCallback(uint32_t linkIndex, Ptr<const Packet> p) {
    if (linkIndex < g_linkStats.size()) g_linkStats[linkIndex].rxPackets++;
}

// ==================== Dijkstra ====================

struct DijkstraResult {
    std::vector<double> dist;
    std::vector<int> prev;
};

DijkstraResult Dijkstra(uint32_t src, uint32_t numNodes) {
    DijkstraResult result;
    result.dist.assign(numNodes, std::numeric_limits<double>::infinity());
    result.prev.assign(numNodes, -1);
    result.dist[src] = 0;
    std::priority_queue<std::pair<double, uint32_t>, std::vector<std::pair<double, uint32_t>>, std::greater<std::pair<double, uint32_t>>> pq;
    pq.push({0, src});
    while (!pq.empty()) {
        auto [d, u] = pq.top(); pq.pop();
        if (d > result.dist[u]) continue;
        for (auto& [v, w] : g_adjList[u]) {
            if (result.dist[u] + w < result.dist[v]) {
                result.dist[v] = result.dist[u] + w;
                result.prev[v] = u;
                pq.push({result.dist[v], v});
            }
        }
    }
    return result;
}

std::vector<uint32_t> GetPath(uint32_t src, uint32_t dst, const DijkstraResult& dijkstra) {
    std::vector<uint32_t> path;
    if (dijkstra.dist[dst] == std::numeric_limits<double>::infinity()) return path;
    for (int at = dst; at != -1; at = dijkstra.prev[at]) path.push_back(at);
    std::reverse(path.begin(), path.end());
    return path;
}

// ==================== 加载数据 ====================

bool LoadLinks(const std::string& file) {
    std::ifstream f(file.c_str());
    if (!f.is_open()) { std::cerr << "Cannot open: " << file << std::endl; return false; }
    std::string line; std::getline(f, line); 
    while (std::getline(f, line)) {
        if (Trim(line).empty()) continue;
        std::stringstream ss(line); std::string tok; LinkParam p;
        try {
            std::getline(ss, tok, ','); p.srcId = std::stoul(Trim(tok));
            std::getline(ss, tok, ','); p.dstId = std::stoul(Trim(tok));
            std::getline(ss, tok, ','); p.srcName = Trim(tok);
            std::getline(ss, tok, ','); p.dstName = Trim(tok);
            std::getline(ss, tok, ','); p.delayMs = std::stod(Trim(tok));
            std::getline(ss, tok, ','); p.dataRateBps = std::stoull(Trim(tok));
            if (std::getline(ss, tok, ',')) p.packetLossRate = std::stod(Trim(tok)); else p.packetLossRate = 0;
            if (std::getline(ss, tok, ',')) p.distanceKm = std::stod(Trim(tok)); else p.distanceKm = 0;
            if (p.delayMs <= 0) p.delayMs = 1.0;
            if (p.dataRateBps < 1000) p.dataRateBps = 1000000;
            g_links.push_back(p);
            g_nodeIdToName[p.srcId] = p.srcName; g_nodeIdToName[p.dstId] = p.dstName;
            uint32_t m = std::max(p.srcId, p.dstId) + 1;
            if (m > g_numNodes) g_numNodes = m;
        } catch (...) { continue; }
    }
    f.close();
    g_adjList.resize(g_numNodes);
    for (const auto& link : g_links) {
        g_adjList[link.srcId].push_back({link.dstId, link.delayMs});
        g_adjList[link.dstId].push_back({link.srcId, link.delayMs});
    }
    std::cout << "Loaded " << g_links.size() << " links\n";
    return !g_links.empty();
}

bool LoadDemands(const std::string& file) {
    std::ifstream f(file.c_str());
    if (!f.is_open()) return false;
    std::string line; std::getline(f, line);
    while (std::getline(f, line)) {
        if (Trim(line).empty()) continue;
        std::stringstream ss(line); std::string tok; TrafficDemand d;
        try {
            std::getline(ss, tok, ','); d.demandId = std::stoul(Trim(tok));
            std::getline(ss, tok, ','); d.srcNode = Trim(tok);
            std::getline(ss, tok, ','); d.dstNode = Trim(tok);
            std::getline(ss, tok, ','); d.srcId = std::stoul(Trim(tok));
            std::getline(ss, tok, ','); d.dstId = std::stoul(Trim(tok));
            std::getline(ss, tok, ','); d.dataRateMbps = std::stod(Trim(tok));
            std::getline(ss, tok, ','); d.startTimeSec = std::stod(Trim(tok));
            std::getline(ss, tok, ','); d.durationSec = std::stod(Trim(tok));
            g_demands.push_back(d);
        } catch (...) { continue; }
    }
    f.close();
    std::cout << "Loaded " << g_demands.size() << " traffic demands\n";
    return !g_demands.empty();
}

std::string GetSatelliteName(const Ipv4Address& addr) {
    std::ostringstream oss; oss << addr;
    auto it = g_ipToSatellite.find(oss.str());
    return (it != g_ipToSatellite.end()) ? it->second : "Unknown";
}
std::string GetNodeName(uint32_t nodeId) {
    auto it = g_nodeIdToName.find(nodeId);
    return (it != g_nodeIdToName.end()) ? it->second : "Node_" + std::to_string(nodeId);
}

void SaveResults(const std::string& file, Ptr<FlowMonitor> mon, Ptr<Ipv4FlowClassifier> cls) {
    std::ofstream f(file.c_str());
    f << "FlowId,SrcAddr,DstAddr,SrcSatellite,DstSatellite,TxPackets,RxPackets,LostPackets,"
      << "Throughput_Mbps,MeanDelay_ms,MeanJitter_ms,PacketLossRate\n";
    FlowMonitor::FlowStatsContainer stats = mon->GetFlowStats();
    for (auto it = stats.begin(); it != stats.end(); ++it) {
        Ipv4FlowClassifier::FiveTuple t = cls->FindFlow(it->first);
        uint64_t lost = (it->second.txPackets > it->second.rxPackets) ? (it->second.txPackets - it->second.rxPackets) : 0;
        double tp = 0, dl = 0, jt = 0, pl = 0;
        if (it->second.txPackets > 0) pl = (double)lost / it->second.txPackets;
        if (it->second.rxPackets > 0) {
            double dur = it->second.timeLastRxPacket.GetSeconds() - it->second.timeFirstTxPacket.GetSeconds();
            if (dur > 0) tp = it->second.rxBytes * 8.0 / dur / 1e6;
            dl = it->second.delaySum.GetMilliSeconds() / it->second.rxPackets;
            jt = it->second.jitterSum.GetMilliSeconds() / it->second.rxPackets;
        }
        f << it->first << "," << t.sourceAddress << "," << t.destinationAddress << ","
          << GetSatelliteName(t.sourceAddress) << "," << GetSatelliteName(t.destinationAddress) << ","
          << it->second.txPackets << "," << it->second.rxPackets << "," << lost << ","
          << std::fixed << std::setprecision(6) << tp << "," << dl << "," << jt << "," << pl << "\n";
    }
    f.close();
}

void SaveLinkStats(const std::string& file) {
    std::ofstream f(file.c_str());
    f << "SrcNode,DstNode,TxPackets,RxPackets,LostPackets,PacketLossRate\n";
    for (size_t i = 0; i < g_links.size(); ++i) {
        const auto& lp = g_links[i];
        const auto& st = g_linkStats[i];
        uint64_t lost = (st.txPackets >= st.rxPackets) ? (st.txPackets - st.rxPackets) : 0;
        double plr = (st.txPackets > 0) ? (double)lost / st.txPackets : 0.0;
        f << lp.srcName << "," << lp.dstName << ","
          << st.txPackets << "," << st.rxPackets << "," << lost << ","
          << std::fixed << std::setprecision(6) << plr << "\n";
    }
    f.close();
}

// ==================== 主函数 ====================
int main(int argc, char *argv[]) {
    std::string linkFile = "scratch/starlink/data/input/link_params.csv";
    std::string demandFile = "scratch/starlink/data/input/traffic_demands.csv";
    std::string outFile = "scratch/starlink/data/output/flow_results.csv";
    double simTime = 10.0;
    
    CommandLine cmd(__FILE__);
    cmd.AddValue("linkParams", "Link params CSV", linkFile);
    cmd.AddValue("demands", "Traffic demands CSV", demandFile);
    cmd.AddValue("output", "Output CSV", outFile);
    cmd.AddValue("simTime", "Sim time (s)", simTime);
    cmd.Parse(argc, argv);
    
    std::cout << "Links:   " << linkFile << "\nOutput:  " << outFile << "\n";

    g_monitorFile.open("scratch/starlink/data/output/link_monitor.csv");
    g_monitorFile << "Time,SrcNode,DstNode,QueuePackets\n";

    std::string routePathFile = "scratch/starlink/data/output/route_paths.csv";
    std::ofstream routeFile(routePathFile.c_str());
    routeFile << "FlowId,SrcNode,DstNode,HopCount,PathString\n";
    
    if (!LoadLinks(linkFile)) return 1;
    if (!LoadDemands(demandFile)) return 1;
    
    g_linkStats.resize(g_links.size());
    for (size_t i = 0; i < g_links.size(); ++i) {
        g_linkStats[i].srcName = g_links[i].srcName;
        g_linkStats[i].dstName = g_links[i].dstName;
    }
    
    // 创建节点
    g_nodes.Create(g_numNodes);
    
    // 安装协议栈
    InternetStackHelper internet;
    internet.Install(g_nodes);
    
    PointToPointHelper p2p;
    Ipv4AddressHelper ipv4;
    Ipv4StaticRoutingHelper staticRoutingHelper;
    
    uint32_t sub = 0;

    std::cout << "Creating " << g_links.size() << " links...\n";
    for (size_t i = 0; i < g_links.size(); i++) {
        std::ostringstream r, d, b;
        r << g_links[i].dataRateBps << "bps";
        d << g_links[i].delayMs << "ms";
        
        p2p.SetDeviceAttribute("DataRate", StringValue(r.str()));
        p2p.SetChannelAttribute("Delay", StringValue(d.str()));
        p2p.SetQueue("ns3::DropTailQueue", "MaxSize", StringValue("500p"));

        NetDeviceContainer devs = p2p.Install(g_nodes.Get(g_links[i].srcId), g_nodes.Get(g_links[i].dstId));
        
        double plr = g_links[i].packetLossRate;
        if (plr > 0.0 && plr < 1.0) {
            Ptr<RateErrorModel> em = CreateObject<RateErrorModel>();
            em->SetAttribute("ErrorRate", DoubleValue(plr));
            em->SetAttribute("ErrorUnit", StringValue("ERROR_UNIT_PACKET"));
            devs.Get(0)->SetAttribute("ReceiveErrorModel", PointerValue(em));
            devs.Get(1)->SetAttribute("ReceiveErrorModel", PointerValue(em));
        }
        
        g_monitoredLinks.push_back({
            g_links[i].srcName, 
            g_links[i].dstName, 
            DynamicCast<PointToPointNetDevice>(devs.Get(0))
        });
        g_monitoredLinks.push_back({
            g_links[i].dstName, 
            g_links[i].srcName, 
            DynamicCast<PointToPointNetDevice>(devs.Get(1))
        });

        devs.Get(0)->TraceConnectWithoutContext("MacTx", MakeBoundCallback(&LinkTxCallback, static_cast<uint32_t>(i)));
        devs.Get(1)->TraceConnectWithoutContext("MacRx", MakeBoundCallback(&LinkRxCallback, static_cast<uint32_t>(i)));
        
        b << "10." << (sub/256)%256 << "." << sub%256 << ".0";
        ipv4.SetBase(b.str().c_str(), "255.255.255.252");
        Ipv4InterfaceContainer ifaces = ipv4.Assign(devs);
        
        // 记录链路接口信息（用于后续设置静态路由）
        uint32_t srcId = g_links[i].srcId;
        uint32_t dstId = g_links[i].dstId;
        
        // 获取接口索引
        Ptr<Ipv4> srcIpv4 = g_nodes.Get(srcId)->GetObject<Ipv4>();
        Ptr<Ipv4> dstIpv4 = g_nodes.Get(dstId)->GetObject<Ipv4>();
        uint32_t srcIfIndex = srcIpv4->GetNInterfaces() - 1;
        uint32_t dstIfIndex = dstIpv4->GetNInterfaces() - 1;
        
        // 保存：从 srcId 到 dstId，使用接口 srcIfIndex，下一跳是 ifaces.GetAddress(1)
        g_linkInterface[{srcId, dstId}] = {srcIfIndex, ifaces.GetAddress(1)};
        // 反向
        g_linkInterface[{dstId, srcId}] = {dstIfIndex, ifaces.GetAddress(0)};
        
        std::ostringstream srcIp, dstIp;
        srcIp << ifaces.GetAddress(0); dstIp << ifaces.GetAddress(1);
        g_ipToSatellite[srcIp.str()] = g_links[i].srcName;
        g_ipToSatellite[dstIp.str()] = g_links[i].dstName;
        if (g_nodeFirstIp.find(g_links[i].srcId) == g_nodeFirstIp.end()) g_nodeFirstIp[g_links[i].srcId] = ifaces.GetAddress(0);
        if (g_nodeFirstIp.find(g_links[i].dstId) == g_nodeFirstIp.end()) g_nodeFirstIp[g_links[i].dstId] = ifaces.GetAddress(1);
        sub++;
    }
    
    // 创建流并设置静态路由
    uint16_t port = 9000;
    std::cout << "Creating flows with static routing...\n";
    
    for (const auto& demand : g_demands) {
        uint32_t src = demand.srcId;
        uint32_t dst = demand.dstId;
        
        if (g_nodeFirstIp.find(dst) == g_nodeFirstIp.end()) continue;
        
        // 计算最短路径
        DijkstraResult dijkstra = Dijkstra(src, g_numNodes);
        std::vector<uint32_t> path = GetPath(src, dst, dijkstra);
        
        if (path.empty() || path.size() < 2) continue;

        // 记录路径
        std::ostringstream pathSs;
        for (size_t j = 0; j < path.size(); j++) {
            pathSs << GetNodeName(path[j]);
            if (j < path.size() - 1) pathSs << "->";
        }
        routeFile << (demand.demandId + 1) << "," << demand.srcNode << "," << demand.dstNode << ","
                  << (path.size() - 1) << "," << pathSs.str() << "\n";
        
        std::cout << "  Flow " << demand.demandId << ": " << pathSs.str() << "\n";

        // 获取目的地址
        Ipv4Address destAddr = g_nodeFirstIp[dst];
        
        // 【关键】为路径上的每一跳设置静态路由
        for (size_t hop = 0; hop < path.size() - 1; hop++) {
            uint32_t currentNode = path[hop];
            uint32_t nextNode = path[hop + 1];
            
            // 查找接口信息
            auto it = g_linkInterface.find({currentNode, nextNode});
            if (it == g_linkInterface.end()) {
                std::cerr << "Warning: No interface found for " << currentNode << " -> " << nextNode << "\n";
                continue;
            }
            
            uint32_t ifIndex = it->second.first;
            Ipv4Address nextHopAddr = it->second.second;
            
            // 获取静态路由
            Ptr<Ipv4> ipv4Node = g_nodes.Get(currentNode)->GetObject<Ipv4>();
            Ptr<Ipv4StaticRouting> staticRouting = staticRoutingHelper.GetStaticRouting(ipv4Node);
            
            // 添加到目的地的路由
            staticRouting->AddHostRouteTo(destAddr, nextHopAddr, ifIndex);
        }
        
        // 创建应用
        PacketSinkHelper sink("ns3::UdpSocketFactory", InetSocketAddress(Ipv4Address::GetAny(), port));
        ApplicationContainer sinkApps = sink.Install(g_nodes.Get(dst));
        sinkApps.Start(Seconds(0.0));
        sinkApps.Stop(Seconds(simTime));
        
        std::ostringstream rateStr;
        rateStr << demand.dataRateMbps << "Mbps";
        OnOffHelper onoff("ns3::UdpSocketFactory", InetSocketAddress(destAddr, port));
        onoff.SetAttribute("DataRate", StringValue(rateStr.str()));
        onoff.SetAttribute("PacketSize", UintegerValue(1024));
        onoff.SetAttribute("OnTime", StringValue("ns3::ExponentialRandomVariable[Mean=1.0]"));
        onoff.SetAttribute("OffTime", StringValue("ns3::ExponentialRandomVariable[Mean=0.5]"));
        
        ApplicationContainer clientApps = onoff.Install(g_nodes.Get(src));
        clientApps.Start(Seconds(demand.startTimeSec));
        clientApps.Stop(Seconds(demand.startTimeSec + demand.durationSec));
        port++;
    }

    routeFile.flush(); routeFile.close();
    
    FlowMonitorHelper fmHelper;
    Ptr<FlowMonitor> monitor = fmHelper.InstallAll();
    
    Simulator::Schedule(Seconds(0.1), &MonitorQueues, 0.1);

    std::cout << "Running " << simTime << "s simulation...\n";
    Simulator::Stop(Seconds(simTime));
    Simulator::Run();
    
    Ptr<Ipv4FlowClassifier> classifier = DynamicCast<Ipv4FlowClassifier>(fmHelper.GetClassifier());
    SaveResults(outFile, monitor, classifier);
    
    g_monitoredLinks.clear();
    g_monitorFile.flush();
    g_monitorFile.close();
    
    Simulator::Destroy();
    
    std::string linkStatsFile = "scratch/starlink/data/output/link_stats.csv";
    SaveLinkStats(linkStatsFile);
    
    return 0;
}
