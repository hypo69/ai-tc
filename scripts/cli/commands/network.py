# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Scripts Cli Commands - Network
# =============================================================================
# Description:
#   Команды захвата сетевого трафика и анализа TShark (network).
#
# Usage Examples:
#   Python API:
#     from scripts.cli.commands.network import register_network_parser
#
#     res = register_network_parser()
#
# File: network.py
# Project: ai-windows-admin
# Package: scripts.cli.commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 13:24:00
# =============================================================================

from __future__ import annotations
from logger import logger
"""Команды захвата сетевого трафика и анализа TShark (network)."""

import argparse


def register_network_parser(subparsers: argparse._SubParsersAction) -> None:
    """Регистрация аргументов команды network."""
    network_parser = subparsers.add_parser('network', help='Network traffic capture and TShark analysis')
    network_subparsers = network_parser.add_subparsers(dest='subcommand', help='Subcommands')
    network_subparsers.add_parser('status', help='Check TShark binary status')
    network_subparsers.add_parser('interfaces', help='List available network interfaces')
    network_devices = network_subparsers.add_parser('devices', help='List discovered devices on local network')
    network_devices.add_argument('--scan', '-s', action='store_true', help='Trigger active ARP/SSDP scan')
    network_devices.add_argument('--subnet', help='Target subnet CIDR (e.g. 192.168.1.0/24)')
    network_analyze = network_subparsers.add_parser('analyze', help='Analyze PCAP file')
    network_analyze.add_argument('--file', '-f', required=True, help='Path to .pcap or .pcapng file')
    network_analyze.add_argument('--filter', '-Y', default='', help='Wireshark display filter')


def run_network_command(args: argparse.Namespace) -> int:
    """Анализ PCAP трафика и проверка доступности TShark."""
    from apps.tshark import TSharkWrapper, TrafficAnalyzer
    sub = args.subcommand
    wrapper = TSharkWrapper()
    if sub == 'status':
        logger.console(f'TShark Available: {wrapper.is_available()}')
        logger.console(f"TShark Binary Path: {wrapper.tshark_path or 'Not Found'}")
        return 0
    if sub == 'interfaces':
        if not wrapper.is_available():
            logger.console('Error: TShark is not available on this host.')
            return 1
        ifaces = wrapper.list_interfaces()
        logger.console('\n--- NETWORK CAPTURE INTERFACES ---')
        for iface in ifaces:
            logger.console(f'[{iface.id}] {iface.name} - {iface.description}')
        logger.console('----------------------------------\n')
        return 0
    if sub == 'devices':
        from apps.windows.network.lan_scanner import WindowsLanScanner
        scanner = WindowsLanScanner()
        full_scan = bool(getattr(args, 'scan', False))
        subnet = getattr(args, 'subnet', None)
        logger.console(f"[*] {'Сканирование' if full_scan else 'Чтение кеша'} устройств локальной сети{' в ' + subnet if subnet else ''}...")
        devices = scanner.discover_devices(full_scan=full_scan, subnet_cidr=subnet)
        logger.console(f'\nНайдено {len(devices)} устройств в локальной сети:')
        logger.console(f"{'IP Адрес':<18} {'MAC Адрес':<19} {'Производитель':<20} {'Имя хоста':<22} {'Статус'}")
        logger.console('-' * 95)
        for d in devices:
            tag = ' [ШЛЮЗ]' if d.is_gateway else ' [ЛОКАЛЬНЫЙ]' if d.is_local else ''
            vendor_str = (d.vendor or 'Неизвестно')[:19]
            hostname_str = (d.hostname or '-')[:21]
            mac_str = d.mac or '-'
            logger.console(f"{d.ip:<18} {mac_str:<19} {vendor_str:<20} {hostname_str:<22} {d.state}{tag}")
        logger.console('-' * 95 + '\n')
        return 0
    if sub == 'analyze':
        pcap_file = getattr(args, 'file', '')
        if not pcap_file:
            logger.console('Error: --file argument is required for PCAP analysis.')
            return 1
        if not wrapper.is_available():
            logger.console('Error: TShark is not available on this host.')
            return 1
        packets = wrapper.read_pcap(pcap_file, display_filter=getattr(args, 'filter', '') or '')
        analyzer = TrafficAnalyzer()
        stats = analyzer.compute_stats(packets)
        heuristics = analyzer.detect_heuristics(packets)
        logger.console('\n--- PCAP TRAFFIC REPORT ---')
        logger.console(f'Total Packets: {stats.total_packets}')
        logger.console(f'Total Volume: {stats.total_bytes} bytes')
        logger.console(f'Protocol Distribution: {stats.protocol_distribution}')
        logger.console(f'Top Sources: {stats.top_sources}')
        logger.console(f'Top Destinations: {stats.top_destinations}')
        if heuristics:
            logger.console('\nWarnings / Heuristics:')
            for h in heuristics:
                logger.console(f'  [!] {h}')
        logger.console('---------------------------\n')
        return 0
    logger.console(f'Unknown network subcommand: {sub}')
    return 1

