import { useState, useEffect, useRef, useCallback } from 'react';

export function useWebSocket(url) {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const eventIdRef = useRef(0);
  const shouldReconnectRef = useRef(true);
  const reconnectTimerRef = useRef(null);

  const connect = useCallback(() => {
    if (!url) return;

    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}${url}?last_event_id=${eventIdRef.current}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => setConnected(true);

    ws.onclose = (evt) => {
      setConnected(false);
      // Don't reconnect if server explicitly closed:
      // 1000 = normal close, 4000 = run finished, 4004 = run not found
      const serverSaidStop = evt.code === 1000 || evt.code === 4000 || evt.code === 4004;
      if (serverSaidStop) {
        shouldReconnectRef.current = false;
      }
      if (shouldReconnectRef.current && url) {
        reconnectTimerRef.current = setTimeout(connect, 3000);
      }
    };

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data);
        data._id = eventIdRef.current++;
        setEvents(prev => [...prev, data]);

        // Stop reconnecting if run is done or server says stop
        if (['complete', 'completed', 'failed', 'cancelled', 'error'].includes(data.type)) {
          shouldReconnectRef.current = false;
        }
        if (data.data && data.data.stop_reconnect) {
          shouldReconnectRef.current = false;
        }
      } catch {
        // Ignore non-JSON messages
      }
    };

    ws.onerror = () => {
      // Don't call ws.close() here — it triggers onclose which may reconnect.
      // Let the browser handle the error → onclose will fire naturally.
    };

    wsRef.current = ws;
  }, [url]);

  useEffect(() => {
    shouldReconnectRef.current = !!url;
    if (url) {
      connect();
    } else {
      // url changed to null — kill any existing connection
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    }
    return () => {
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      wsRef.current?.close();
    };
  }, [connect, url]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connected, clearEvents };
}
