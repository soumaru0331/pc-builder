"""毎日深夜2時(JST)に全カテゴリを自動同期するスケジューラ"""
import asyncio
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Tokyo")


def _run_scheduled_sync():
    """スケジューラから呼ばれる同期タスク（非同期をブロッキングで実行）"""
    from routers.sync import _run_sync, _sync_status
    from sync.kakaku_sync import KAKAKU_CATEGORIES

    if _sync_status.get("running"):
        logger.info("スケジュール同期: すでに同期中のためスキップ")
        return

    logger.info("スケジュール同期: 開始 (全カテゴリ × 最大150ページ)")
    categories = list(KAKAKU_CATEGORIES.keys())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_sync(categories, max_pages=150, trigger="scheduled"))
        logger.info("スケジュール同期: 完了")
    except Exception as e:
        logger.error(f"スケジュール同期: エラー - {e}")
    finally:
        loop.close()


def start_scheduler():
    """スケジューラを起動する（毎日深夜2時 JST）"""
    scheduler.add_job(
        _run_scheduled_sync,
        trigger=CronTrigger(hour=2, minute=0, timezone="Asia/Tokyo"),
        id="daily_sync",
        name="毎日深夜2時 kakaku.com全カテゴリ同期",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("スケジューラ起動: 毎日 02:00 JST に自動同期")


def stop_scheduler():
    """スケジューラを停止する"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("スケジューラ停止")
