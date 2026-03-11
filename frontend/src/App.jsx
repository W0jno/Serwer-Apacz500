import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Button,
  List,
  ListItem,
  ListItemText,
  Container,
  CircularProgress
} from '@mui/material';
import {
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
} from '@mui/icons-material';

import DeviceItem from '../components/DeviceItem.jsx'
import DeviceDetails from '../components/DeviceDetails.jsx'
import Header from '../components/Header.jsx'
import SessionGraph from '../components/SessionGraph.jsx';

const getTimestamp = () => new Date().toLocaleTimeString();

export default function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [devices, setDevices] = useState({});
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sessionGraph, setSessionGraph] = useState({});

  const logEndRef = useRef(null);
  const socketRef = useRef(null);

  const addLog = useCallback((message) => {
    setLogs((prev) => [...prev, { time: getTimestamp(), message }]);
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  useEffect(() => {
    const wsUrl = `ws://${window.location.hostname}:5000/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
      addLog('Connected to server');
      setLoading(false);
    };

    ws.onclose = () => {
      setIsConnected(false);
      addLog('Disconnected from server');
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      addLog('Connection error occurred');
      setIsConnected(false);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        const { event: eventName, data } = message;

        switch (eventName) {
          case 'connection_confirmed':
            addLog(`Connection confirmed - Server time: ${data.server_time}`);
            break;

          case 'devices_data':
            setDevices(data);
            addLog(`Loaded ${Object.keys(data).length} devices`);
            setLoading(false);
            break;

          case 'device_update':
            setDevices((prev) => ({
              ...prev,
              [data.device_id]: data.data
            }));
            addLog(`${data.device_id}: ${data.data.status ? 'online' : 'offline'}, ${data.data.charge_level}%`);
            break;

          case 'device_removed':
            setDevices((prev) => {
              const newDevices = { ...prev };
              delete newDevices[data.device_id];
              return newDevices;
            });
            addLog(`Device ${data.device_id} removed`);
            break;

          case 'session_status':
            addLog(`Session ${data.action} - Status: ${data.active ? 'active' : 'inactive'}`);
            break;

          case 'session_matrix_update':
            setSessionGraph(data);
            addLog('Session matrix updated');
            break;

          default:
            console.log('Unknown event:', eventName);
        }
      } catch (e) {
        console.error('Error parsing message', e);
      }
    };

    socketRef.current = ws;

    return () => {
      ws.close();
      socketRef.current = null;
    };
  }, [addLog]);

  const handleDeviceSelect = (deviceId, isSelected) => {
    if (socketRef.current && isConnected) {
      socketRef.current.send(JSON.stringify({
        event: 'device_selected',
        data: { device_id: deviceId, selected: isSelected }
      }));

      setDevices(prev => ({
        ...prev,
        [deviceId]: { ...prev[deviceId], selected: isSelected }
      }));
    }
  };

  const handleDeviceStatus = (deviceId, newStatus) => {
    if (socketRef.current && isConnected) {
      socketRef.current.send(JSON.stringify({
        event: 'device_status_change',
        data: { device_id: deviceId, status: newStatus }
      }));

      addLog(`Sending status command to ${deviceId}: ${newStatus ? 'ON' : 'OFF'}`);

      setDevices(prev => ({
        ...prev,
        [deviceId]: { ...prev[deviceId], status: newStatus }
      }));
    }
  };

  const handleDeviceCommand = (deviceId, actuator, value) => {
    if (socketRef.current && isConnected) {
      socketRef.current.send(JSON.stringify({
        event: 'device_command',
        data: { device_id: deviceId, actuator, value }
      }));

      addLog(`Command -> ${deviceId}: actuator=${actuator}, value=${JSON.stringify(value)}`);
    }
  };

  const handleSessionAction = (action) => {
    if (socketRef.current && isConnected) {
      socketRef.current.send(JSON.stringify({
        event: action === 'start' ? 'start_session' : 'stop_session',
        data: {}
      }));
    }
    const key = `${componentType}:${name}`;
    setComponentStates((prev) => ({
      ...prev,
      [deviceId]: { ...(prev[deviceId] || {}), [key]: state }
    }));
    addLog(`${deviceId} → ${componentType} ${name}: ${state ? 'ON' : 'OFF'}`);
  };

  return (
    <Box sx={{ flexGrow: 1, height: '100vh', width: '100vw', display: 'flex', flexDirection: 'column', bgcolor: '#f5f5f5' }}>
      <Header isConnected={isConnected} />

      <Container maxWidth={false} sx={{ flexGrow: 1, py: 2, overflow: 'hidden' }}>
        <Grid container spacing={2} sx={{ height: '100%', width: '100%' }}>
          <Grid item size={3} sx={{ height: '100%' }}>
            <Paper sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <Box p={2} borderBottom={1} borderColor="divider">
                <Typography variant="h6">Devices</Typography>
              </Box>

              <Box sx={{ flexGrow: 1, overflowY: 'auto', p: 2, bgcolor: '#fafafa' }}>
                {loading ? (
                  <Box display="flex" flexDirection="column" alignItems="center" mt={4}>
                    <CircularProgress size={30} />
                    <Typography variant="caption" mt={1}>Loading devices...</Typography>
                  </Box>
                ) : Object.keys(devices).length === 0 ? (
                  <Box textAlign="center" mt={4} color="text.secondary">
                    <Typography fontStyle="italic">No devices found</Typography>
                    <Typography variant="caption">Waiting for MQTT messages...</Typography>
                  </Box>
                ) : (
                  Object.keys(devices).map((deviceId) => (
                    <DeviceItem
                      key={deviceId}
                      deviceId={deviceId}
                      data={devices[deviceId]}
                      onToggleSelect={handleDeviceSelect}
                      onToggleStatus={handleDeviceStatus}
                      onSendCommand={handleDeviceCommand}
                    />
                  ))
                )}
              </Box>
            </Paper>
          </Grid>

          <Grid item size={9} sx={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Paper sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#fafafa', m: 2, border: '2px dashed #ddd', borderRadius: 2 }}>
                <SessionGraph graph={sessionGraph} />
              </Box>

              <Box p={2} borderTop={1} borderColor="divider" display="flex" justifyContent="center" gap={2}>
                <Button variant="contained" color="success" startIcon={<PlayArrowIcon />} onClick={() => handleSessionAction('start')} disabled={!isConnected}>
                  Start Sesji
                </Button>
                <Button variant="contained" color="error" startIcon={<StopIcon />} onClick={() => handleSessionAction('stop')} disabled={!isConnected}>
                  Zatrzymanie Sesji
                </Button>
              </Box>
            </Paper>

            <Paper sx={{ height: '200px', display: 'flex', flexDirection: 'column' }}>
              <Box p={1} px={2} borderBottom={1} borderColor="divider" bgcolor="#f8f9fa">
                <Typography variant="subtitle2">Connection Log</Typography>
              </Box>
              <List dense sx={{ flexGrow: 1, overflowY: 'auto', bgcolor: '#fafafa', fontFamily: 'monospace' }}>
                {logs.map((log, index) => (
                  <ListItem key={index} sx={{ py: 0 }}>
                    <ListItemText
                      primary={
                        <Typography variant="body2" component="span" sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                          <Box component="span" color="text.secondary" mr={1}>[{log.time}]</Box>
                          {log.message}
                        </Typography>
                      }
                    />
                  </ListItem>
                ))}
                <div ref={logEndRef} />
              </List>
            </Paper>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
}
