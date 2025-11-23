import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Checkbox,
  FormControlLabel,
  Button,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  Chip,
  Container,
  Stack,
  CircularProgress
} from '@mui/material';
import {
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
} from '@mui/icons-material';

import DeviceItem from '../components/DeviceItem.jsx'
import Header from '../components/Header.jsx'

// Formatowanie czasu dla logów
const getTimestamp = () => new Date().toLocaleTimeString();

// --- Main Application Component ---

export default function App() {
  const [socket, setSocket] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [devices, setDevices] = useState({});
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Ref do automatycznego scrollowania logów
  const logEndRef = useRef(null);

  // Funkcja dodawania logów
  const addLog = useCallback((message) => {
    setLogs((prev) => [...prev, { time: getTimestamp(), message }]);
  }, []);

  // Automatyczny scroll do dołu logów
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // --- WebSocket Connection Logic ---
  useEffect(() => {
    // Używamy natywnego WebSocket zgodnie z backendem FastAPI
    const wsUrl = `ws://${window.location.hostname}:5000/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
      addLog("Connected to server");
      setLoading(false);
    };

    ws.onclose = () => {
      setIsConnected(false);
      addLog("Disconnected from server");
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      addLog("Connection error occurred");
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
            const status = data.data.status ? true : false;
            // Opcjonalnie: odkomentuj jeśli chcesz logować każdą aktualizację (może spamować)
            addLog(`${data.device_id}: ${status}, ${data.data.charge_level}%`);
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
            
          default:
            console.log("Unknown event:", eventName);
        }
      } catch (e) {
        console.error("Error parsing message", e);
      }
    };

    setSocket(ws);

    return () => {
      ws.close();
    };
  }, [addLog]);

  // --- Actions ---

  const handleDeviceSelect = (deviceId, isSelected) => {
    if (socket && isConnected) {
      socket.send(JSON.stringify({
        event: "device_selected",
        data: { device_id: deviceId, selected: isSelected }
      }));
      // Aktualizujemy lokalnie optymistycznie
      setDevices(prev => ({
        ...prev,
        [deviceId]: { ...prev[deviceId], selected: isSelected }
      }));
    }
  };

  const handleSessionAction = (action) => {
    if (socket && isConnected) {
      socket.send(JSON.stringify({
        event: action === 'start' ? "start_session" : "stop_session",
        data: {}
      }));
    }
  };

  return (
    <Box sx={{ flexGrow: 1, height: '100vh', width:'100vw', display: 'flex', flexDirection: 'column', bgcolor: '#f5f5f5' }}>
      
      {/* Header */}
      <Header isConnected={isConnected}></Header>
      {/* Main Content */}
      <Container maxWidth={false} sx={{ flexGrow: 1, py: 2, overflow: 'hidden' }}>
        <Grid container spacing={2} sx={{ height: '100%', width:'100%' }}>
          
          {/* Left Panel: Devices */}
          <Grid item size={2} sx={{ height: '100%' }}>
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
                    />
                  ))
                )}
              </Box>
            </Paper>
          </Grid>

          {/* Middle/Right Area */}
          <Grid item size={10} sx={{height: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
            
            {/* Graph / Main Workspace */}
            <Paper sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#fafafa', m: 2, border: '2px dashed #ddd', borderRadius: 2 }}>
                <Typography variant="h5" color="text.secondary">Graph Area</Typography>
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

            {/* Log Container */}
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