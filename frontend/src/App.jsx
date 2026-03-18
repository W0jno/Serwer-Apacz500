import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
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
  CircularProgress,
  TextField,
  Select,
  MenuItem,
  Stack,
  Divider,
  IconButton,
} from '@mui/material';
import {
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';

import DeviceItem from '../components/DeviceItem.jsx';
import Header from '../components/Header.jsx';
import SessionGraph from '../components/SessionGraph.jsx';

const getTimestamp = () => new Date().toLocaleTimeString();

export default function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [devices, setDevices] = useState({});
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sessionGraph, setSessionGraph] = useState({});
  const [dependencyRules, setDependencyRules] = useState([]);

  const [sourceDeviceId, setSourceDeviceId] = useState('');
  const [sourceEmitter, setSourceEmitter] = useState('default');
  const [triggerState, setTriggerState] = useState('on');
  const [targetDeviceId, setTargetDeviceId] = useState('');
  const [targetTopic, setTargetTopic] = useState('');
  const [payloadText, setPayloadText] = useState('{"command":"actuator","name":"lamp","state":true}');

  const logEndRef = useRef(null);
  const socketRef = useRef(null);

  const deviceIds = useMemo(() => Object.keys(devices), [devices]);
  const sourceEmitters = useMemo(() => {
    if (!sourceDeviceId || !devices[sourceDeviceId]) return ['default'];
    const emitters = devices[sourceDeviceId].emitters;
    return Array.isArray(emitters) && emitters.length > 0 ? emitters : ['default'];
  }, [devices, sourceDeviceId]);

  useEffect(() => {
    if (deviceIds.length === 0) return;
    if (!sourceDeviceId) setSourceDeviceId(deviceIds[0]);
    if (!targetDeviceId) setTargetDeviceId(deviceIds[0]);
  }, [deviceIds, sourceDeviceId, targetDeviceId]);

  useEffect(() => {
    if (!sourceEmitters.includes(sourceEmitter)) {
      setSourceEmitter(sourceEmitters[0] ?? 'default');
    }
  }, [sourceEmitters, sourceEmitter]);

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
              [data.device_id]: data.data,
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

          case 'dependencies_updated':
            setDependencyRules(Array.isArray(data.rules) ? data.rules : []);
            addLog(`Dependency rules updated (${(data.rules || []).length})`);
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
      socketRef.current.send(
        JSON.stringify({
          event: 'device_selected',
          data: { device_id: deviceId, selected: isSelected },
        })
      );

      setDevices((prev) => ({
        ...prev,
        [deviceId]: { ...prev[deviceId], selected: isSelected },
      }));
    }
  };

  const handleDeviceStatus = (deviceId, newStatus) => {
    if (socketRef.current && isConnected) {
      socketRef.current.send(
        JSON.stringify({
          event: 'device_status_change',
          data: { device_id: deviceId, status: newStatus },
        })
      );

      addLog(`Sending status command to ${deviceId}: ${newStatus ? 'ON' : 'OFF'}`);

      setDevices((prev) => ({
        ...prev,
        [deviceId]: { ...prev[deviceId], status: newStatus },
      }));
    }
  };

  const handleDeviceCommand = (deviceId, actuator, value) => {
    if (socketRef.current && isConnected) {
      socketRef.current.send(
        JSON.stringify({
          event: 'device_command',
          data: { device_id: deviceId, actuator, value },
        })
      );

      addLog(`Command -> ${deviceId}: actuator=${actuator}, value=${JSON.stringify(value)}`);
    }
  };

  const handleSessionAction = (action) => {
    if (socketRef.current && isConnected) {
      socketRef.current.send(
        JSON.stringify({
          event: action === 'start' ? 'start_session' : 'stop_session',
          data: {},
        })
      );
    }
  };

  const handleCreateDependency = () => {
    if (!socketRef.current || !isConnected) return;
    if (!sourceDeviceId || !targetDeviceId) {
      addLog('Dependency create failed: source/target device missing');
      return;
    }

    let payload;
    try {
      payload = JSON.parse(payloadText);
    } catch {
      addLog('Dependency create failed: payload JSON is invalid');
      return;
    }

    socketRef.current.send(
      JSON.stringify({
        event: 'create_dependency',
        data: {
          source_device_id: sourceDeviceId,
          source_emitter: sourceEmitter,
          trigger_state: triggerState,
          target_device_id: targetDeviceId,
          target_topic: targetTopic,
          payload,
          enabled: true,
        },
      })
    );

    addLog(`Dependency created: ${sourceDeviceId}/${sourceEmitter}(${triggerState}) -> ${targetDeviceId}`);
  };

  const handleDeleteDependency = (ruleId) => {
    if (!socketRef.current || !isConnected) return;

    socketRef.current.send(
      JSON.stringify({
        event: 'delete_dependency',
        data: { rule_id: ruleId },
      })
    );

    addLog(`Dependency deleted: ${ruleId}`);
  };

  return (
    // Dodane: overflowY: 'auto' oraz overflowX: 'hidden' wymuszą pojawienie się suwaka
    <Box sx={{ minHeight: '100vh', width: '100%', display: 'flex', flexDirection: 'column',bgcolor: 'transparent' }}>
      <Header isConnected={isConnected} />

      <Container maxWidth={false} sx={{ py: 2, flexGrow: 1 }}>
        <Grid container spacing={2}>
          
          {/* LEWY PANEL - Urządzenia */}
          <Grid item size={3}>
            <Paper sx={{ display: 'flex', flexDirection: 'column' }}>
              <Box p={2} borderBottom={1} borderColor="divider">
                <Typography variant="h6">Devices</Typography>
              </Box>

              {/* maxHeight pozwala liście urządzeń mieć własny mały scroll, by nie rozciągała strony w kosmos */}
              <Box sx={{ overflowY: 'auto', maxHeight: '80vh', p: 2, bgcolor: '#fafafa' }}>
                {loading ? (
                  <Box display="flex" flexDirection="column" alignItems="center" mt={4}>
                    <CircularProgress size={30} />
                    <Typography variant="caption" mt={1}>
                      Loading devices...
                    </Typography>
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

          {/* PRAWY PANEL */}
          <Grid item size={9} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            
            <Paper sx={{ display: 'flex', flexDirection: 'column' }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: '#fafafa',
                  m: 2,
                  border: '2px dashed #ddd',
                  borderRadius: 2,
                  minHeight: 200
                }}
              >
                <SessionGraph graph={sessionGraph} />
              </Box>

              <Box p={2} borderTop={1} borderColor="divider" display="flex" justifyContent="center" gap={2}>
                <Button
                  variant="contained"
                  color="success"
                  startIcon={<PlayArrowIcon />}
                  onClick={() => handleSessionAction('start')}
                  disabled={!isConnected}
                >
                  Start Sesji
                </Button>
                <Button
                  variant="contained"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={() => handleSessionAction('stop')}
                  disabled={!isConnected}
                >
                  Zatrzymanie Sesji
                </Button>
              </Box>
            </Paper>

            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" fontWeight="bold" mb={1}>
                Server Dependencies (widget Y ➜ widget X)
              </Typography>
              <Stack spacing={1.2}>
                <Stack direction="row" spacing={1}>
                  <Select size="small" value={sourceDeviceId} onChange={(e) => setSourceDeviceId(e.target.value)} fullWidth>
                    {deviceIds.map((id) => (
                      <MenuItem key={`source-${id}`} value={id}>
                        Source: {id}
                      </MenuItem>
                    ))}
                  </Select>
                  <Select size="small" value={sourceEmitter} onChange={(e) => setSourceEmitter(e.target.value)} fullWidth>
                    {sourceEmitters.map((emitter) => (
                      <MenuItem key={`emitter-${emitter}`} value={emitter}>
                        Emitter: {emitter}
                      </MenuItem>
                    ))}
                  </Select>
                  <Select size="small" value={triggerState} onChange={(e) => setTriggerState(e.target.value)}>
                    <MenuItem value="on">on</MenuItem>
                    <MenuItem value="off">off</MenuItem>
                    <MenuItem value="any">any</MenuItem>
                  </Select>
                </Stack>

                <Stack direction="row" spacing={1}>
                  <Select size="small" value={targetDeviceId} onChange={(e) => setTargetDeviceId(e.target.value)} fullWidth>
                    {deviceIds.map((id) => (
                      <MenuItem key={`target-${id}`} value={id}>
                        Target: {id}
                      </MenuItem>
                    ))}
                  </Select>
                  <TextField
                    size="small"
                    fullWidth
                    value={targetTopic}
                    onChange={(e) => setTargetTopic(e.target.value)}
                    placeholder="target topic (empty => <target>/command)"
                  />
                </Stack>

                <TextField
                  size="small"
                  multiline
                  minRows={3}
                  value={payloadText}
                  onChange={(e) => setPayloadText(e.target.value)}
                  placeholder='{"command":"actuator","name":"lamp","state":true}'
                />

                <Box>
                  <Button variant="contained" onClick={handleCreateDependency} disabled={!isConnected || !deviceIds.length}>
                    Add dependency rule
                  </Button>
                </Box>

                <Divider />

                <Typography variant="body2" color="text.secondary">
                  Active rules: {dependencyRules.length}
                </Typography>
                <List dense>
                  {dependencyRules.map((rule) => (
                    <ListItem
                      key={rule.id}
                      secondaryAction={
                        <IconButton edge="end" onClick={() => handleDeleteDependency(rule.id)}>
                          <DeleteIcon />
                        </IconButton>
                      }
                    >
                      <ListItemText
                        primary={`${rule.source_device_id}/${rule.source_emitter} (${rule.trigger_state}) ➜ ${rule.target_topic}`}
                        secondary={JSON.stringify(rule.payload)}
                      />
                    </ListItem>
                  ))}
                </List>
              </Stack>
            </Paper>

            <Paper sx={{ display: 'flex', flexDirection: 'column' }}>
              <Box p={1} px={2} borderBottom={1} borderColor="divider" bgcolor="#f8f9fa">
                <Typography variant="subtitle2">Connection Log</Typography>
              </Box>
              {/* Tutaj też dajemy maxHeight, by logi miały własny scroll, jeśli będzie ich za dużo */}
              <List dense sx={{ overflowY: 'auto', minHeight: '200px', maxHeight: '500px', bgcolor: '#fafafa', fontFamily: 'monospace' }}>
                {logs.map((log, index) => (
                  <ListItem key={index} sx={{ py: 0 }}>
                    <ListItemText
                      primary={
                        <Typography variant="body2" component="span" sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                          <Box component="span" color="text.secondary" mr={1}>
                            [{log.time}]
                          </Box>
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