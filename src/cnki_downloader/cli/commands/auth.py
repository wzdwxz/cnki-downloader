"""cnki login / logout / status — 认证管理命令"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from cnki_downloader.core.auth import (
    check_campus_network,
    check_login_status,
    delete_credential,
    login,
    logout,
    save_credential,
)
from cnki_downloader.core.session import SessionManager
from cnki_downloader.models.user import Credential

console = Console()

auth_app = typer.Typer(name="auth", help="认证管理", no_args_is_help=True)


@auth_app.command(name="login")
def login_command(
    username: str = typer.Option(..., "--username", "-u", prompt="用户名", help="知网账号"),
    password: str = typer.Option(
        ..., "--password", "-p", prompt="密码", hide_input=True, help="密码"
    ),
    remember: bool = typer.Option(False, "--remember", "-r", help="保存凭证到系统密钥环"),
) -> None:
    """登录知网账号。"""
    asyncio.run(_login_async(username, password, remember))


async def _login_async(username: str, password: str, remember: bool) -> None:
    async with SessionManager() as session:
        credential = Credential(username=username, password=password, auth_type="account")

        with console.status("正在登录..."):
            try:
                success = await login(session, credential)
            except Exception as e:
                console.print(f"[red]登录失败: {e}[/red]")
                return

        if success:
            console.print("[green]登录成功[/green]")
            if remember:
                save_credential(credential)
                console.print("[dim]凭证已保存到系统密钥环[/dim]")
        else:
            console.print("[red]登录失败[/red]")


@auth_app.command(name="logout")
def logout_command() -> None:
    """登出知网。"""
    asyncio.run(_logout_async())


async def _logout_async() -> None:
    async with SessionManager() as session:
        await logout(session)
    console.print("[green]已登出[/green]")


@auth_app.command(name="status")
def status_command() -> None:
    """检查当前认证和网络状态。"""
    asyncio.run(_status_async())


async def _status_async() -> None:
    async with SessionManager() as session:
        with console.status("正在检查..."):
            campus = await check_campus_network(session)
            logged_in = await check_login_status(session)

    console.print()
    campus_status = "[green]已连接[/green]" if campus else "[red]未连接[/red]"
    login_status = "[green]已登录[/green]" if logged_in else "[yellow]未登录[/yellow]"
    console.print(f"  校园网/机构网络: {campus_status}")
    console.print(f"  账号登录状态:    {login_status}")

    if campus or logged_in:
        console.print("\n  [green]当前可以访问知网资源[/green]")
    else:
        console.print("\n  [red]当前无法访问知网资源。请连接校园网或登录账号。[/red]")


@auth_app.command(name="forget")
def forget_command(
    username: str = typer.Argument(..., help="要删除凭证的用户名"),
) -> None:
    """删除已保存的登录凭证。"""
    delete_credential(username)
    console.print(f"[green]已删除用户 {username} 的保存凭证[/green]")
