"""
Server-Sent Events (SSE) 엔드포인트
"""

from flask import Blueprint, Response, stream_with_context
import json
import time
import queue
import threading

bp = Blueprint('sse', __name__)

# 전역 이벤트 큐 (클라이언트별)
event_queues = {}
event_queues_lock = threading.Lock()


def send_event(event_type: str, data: dict):
    """모든 연결된 클라이언트에게 이벤트 전송"""
    with event_queues_lock:
        for client_queue in event_queues.values():
            try:
                client_queue.put({
                    'event': event_type,
                    'data': data
                }, block=False)
            except queue.Full:
                pass  # 큐가 가득 차면 무시


@bp.route('/stream/workflow')
def stream_workflow():
    """워크플로우 진행 상황 SSE 스트림"""

    def generate():
        # 클라이언트 ID 생성
        client_id = id(threading.current_thread())

        # 클라이언트 큐 생성
        client_queue = queue.Queue(maxsize=10)

        with event_queues_lock:
            event_queues[client_id] = client_queue

        try:
            # 초기 연결 메시지
            yield f"data: {json.dumps({'type': 'connected', 'message': '연결됨'})}\n\n"

            # 이벤트 대기 및 전송
            while True:
                try:
                    # 이벤트 대기 (5초 타임아웃)
                    event = client_queue.get(timeout=5)

                    # SSE 형식으로 전송
                    event_data = json.dumps(event['data'], ensure_ascii=False)
                    yield f"event: {event['event']}\n"
                    yield f"data: {event_data}\n\n"

                except queue.Empty:
                    # 타임아웃 시 heartbeat 전송 (연결 유지)
                    yield f": heartbeat\n\n"

        finally:
            # 연결 종료 시 큐 제거
            with event_queues_lock:
                event_queues.pop(client_id, None)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Nginx 버퍼링 비활성화
        }
    )


@bp.route('/test-event')
def test_event():
    """SSE 테스트용 엔드포인트"""
    send_event('workflow.test', {
        'message': '테스트 이벤트',
        'timestamp': time.time()
    })
    return {'status': 'sent'}
