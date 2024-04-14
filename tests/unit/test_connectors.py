import unittest
from unittest.mock import patch, MagicMock
from datetime import timedelta
from src.models.models import Command
from src.device.interfaces import IDevice
from pysnmp.proto.rfc1902 import TimeTicks 
from src.connector.conector_factory import ConnectorFactory
from src.connector.netmiko_connector import NetmikoConnector, NetMikoAuthenticationException, NetMikoTimeoutException
from src.connector.snmp_connector import SNMPConnector
from src.connector.rest_connector import RestConnector, ViptelaRestConnector

class TestConnectorFactory(unittest.TestCase):
    
    def setUp(self) -> None:
        self.geral_commandTest = Command(
            command='pode_ser_qlqr)_coisa',
            type='router',
            os='ios',
            vendor='cisco',
            command_name='sysname',
            field='mock',
            group=1,
            parse='mock',
        )
        self.device = MagicMock(spec=IDevice)
        self.device_ip = self.device.get_ip.return_value = '192.168.1.1'
        self.credentials = {
            "vmanage_ip": '1.2.3.4',
            "j_username": 'user',
            "j_password": 'pass',
            "community": "public",
            "username": "user",
            "password": "pass",
        }
        
    @patch('src.connector.conector_factory.ConnectorFactory.create_connector')
    def test_create_connector_w_mock(self, mock_create_connector):
        for connector_name, connector_class in  ConnectorFactory().connectors.items():
            with self.subTest(connector_name=connector_name):
                mock_create_connector.return_value = connector_class
                connector = ConnectorFactory().create_connector(connector_name)
                self.assertIsInstance(connector, (NetmikoConnector, SNMPConnector, RestConnector))

    def test_create_connector_w_no_mock(self):
        for connector_name,_ in ConnectorFactory().connectors.items():
            with self.subTest(connector_name=connector_name):
                connector = ConnectorFactory().create_connector(connector_name)
                self.assertIsInstance(connector, (NetmikoConnector, SNMPConnector, RestConnector))
                
    def test_create_connector_w_no_mock_exception(self):
        with self.assertRaises(Exception) as context:
            ConnectorFactory().create_connector('invalid_connector')
        self.assertEqual(str(context.exception), 'Connector invalid_connector not found')

    @patch('src.connector.snmp_connector.nextCmd')
    def test_snmp_connector_success(self, mock_next_cmd):
        mock_next_cmd.return_value = iter([
            (None, None, None, [(None, MagicMock(prettyPrint=lambda: 'Test SNMP Response'))])
        ])
        
        connector = SNMPConnector()
        result = connector.run(self.device, self.geral_commandTest, self.credentials)
        
        self.assertEqual(result.output, 'Test SNMP Response')
        
    
    @patch('src.connector.snmp_connector.nextCmd')
    def test_snmp_connector_TIMETICKS_success(self, mock_next_cmd):
        time_ticks = TimeTicks(937800)

        mock_next_cmd.return_value = iter([
            (None, None, None, [(None, time_ticks)])
        ])
        
        # Instanciando o conector e executando
        connector = SNMPConnector()
        result = connector.run(self.device, self.geral_commandTest, self.credentials)
        
        # Calculando a saída esperada
        ticks = int(time_ticks.prettyPrint())
        delta = timedelta(seconds=ticks / 100)
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        expected_output = f"{days} days, {hours} hours, {minutes} minutes" if days > 0 else f"{hours} hours, {minutes} minutes"
        
        # Verificações de asserção
        self.assertEqual(result.output, expected_output)
        
    def test_snmp_connector_no_community(self):
        credentials = {}
        connector = SNMPConnector()
        
        result = connector.run(self.device, self.geral_commandTest, credentials)
        self.assertEqual(
            result.error,
            'Community string is required for SNMP'
        )
        
    @patch('src.connector.snmp_connector.nextCmd')
    def test_snmp_connector_errors(self, mock_next_cmd):
        mock_next_cmd.return_value = iter([
            ('error1', None, None, [(None, None)])
        ])
        
        connector = SNMPConnector()
        
        result = connector.run(self.device, self.geral_commandTest, self.credentials)
        
        self.assertEqual(
            result.error,
            'error1'
        )
        
        mock_next_cmd.return_value = iter([
            (None, 'error2', None, [(None, None)])
        ])
        
        
        result = connector.run(self.device, self.geral_commandTest, self.credentials)
        
        self.assertEqual(
            result.error,
            'error2'
        )
        
    @patch('requests.session')
    def test_login_success(self, mock_session):
        mock_session.return_value = MagicMock()
        mock_session.return_value.post.return_value = MagicMock(content=b'')
        mock_session.return_value.get.return_value = MagicMock(content=b'{"mock": "value"}')
        
        connector = ViptelaRestConnector()
        result = connector.run(self.device, self.geral_commandTest, self.credentials)
        
        self.assertEqual(result.output, 'value')
        
    @patch('requests.session')
    def test_login_failed(self, mock_session):
        mock_session.return_value = MagicMock()
        mock_session.return_value.post.return_value = MagicMock(content=b'<html>')
        
        connector = ViptelaRestConnector()
        
        result = connector.run(self.device, self.geral_commandTest, self.credentials)
        
        self.assertEqual(
            result.error,
            'Login Failed at vitptela'
        )
    
    
    #netmiko test
    #SNMPDetect mock
    #SSHDetect mock
    
    @patch('src.connector.netmiko_connector.SNMPDetect', autospec=True)
    @patch('src.connector.netmiko_connector.ConnectHandler')
    def test_netmiko_connector_success_SNMP_DETECT(self, mock_connect_handler, mock_snmp_detect):
        mock_connect_handler.return_value.__enter__.return_value.send_command.return_value = 'Test Netmiko Response'
        mock_snmp_detect.return_value.autodetect.return_value = 'cisco_ios'
        
        connector = NetmikoConnector()
        result = connector.run(self.device, self.geral_commandTest, self.credentials)
        
        self.assertEqual(result.output, 'Test Netmiko Response')    
    
    @patch('src.connector.netmiko_connector.SNMPDetect', autospec=True)
    @patch('src.connector.netmiko_connector.SSHDetect', autospec=True)
    @patch('src.connector.netmiko_connector.ConnectHandler')
    def test_netmiko_connector_success_SSH_DETECT(self, mock_connect_handler, mock_ssh_detect, mock_snmp_detect):
        mock_connect_handler.return_value.__enter__.return_value.send_command.return_value = 'Test Netmiko Response'
        mock_snmp_detect.return_value.autodetect.return_value = None
        mock_ssh_detect.return_value.autodetect.return_value = 'cisco_ios'
        
        
        connector = NetmikoConnector()
        result = connector.run(self.device, self.geral_commandTest, self.credentials)
        
        self.assertEqual(result.output, 'Test Netmiko Response')
    
    @patch('src.connector.netmiko_connector.SNMPDetect', autospec=True)
    @patch('src.connector.netmiko_connector.SSHDetect', autospec=True)
    @patch('src.connector.netmiko_connector.ConnectHandler')
    def test_netmiko_connector_SNMP_DETECT_exception(self, mock_connect_handler, mock_ssh_detect, mock_snmp_detect):
        mock_connect_handler.return_value.__enter__.return_value.send_command.return_value = 'Test Netmiko Response'
        mock_snmp_detect.return_value.autodetect.side_effect = Exception('Test SNMP Detect Exception')
        mock_ssh_detect.return_value.autodetect.return_value = 'cisco_ios'
        
        connector = NetmikoConnector()
        result = connector.run(self.device, self.geral_commandTest, self.credentials)
        
        self.assertEqual(result.error, 'Could not detect device type neither by SNMP nor SSH')
        
    @patch('src.connector.netmiko_connector.SNMPDetect', autospec=True)
    @patch('src.connector.netmiko_connector.SSHDetect', autospec=True)
    @patch('src.connector.netmiko_connector.ConnectHandler')
    def test_netmiko_connector_SSH_DETECT_exception(self, mock_connect_handler, mock_ssh_detect, mock_snmp_detect):
        mock_connect_handler.return_value.__enter__.return_value.send_command.return_value = 'Test Netmiko Response'
        mock_snmp_detect.return_value.autodetect.return_value = None
        mock_ssh_detect.return_value.autodetect.side_effect = Exception('Test SSH Detect Exception')
        
        credentials = {
            'username': 'user',
            'password': 'pass'
        }
        connector = NetmikoConnector()
        result = connector.run(self.device, self.geral_commandTest, credentials)
        
        self.assertEqual(result.error, 'Could not detect device type by SSH')
    
    
    @patch('src.connector.netmiko_connector.SSHDetect', autospec=True)
    def test_netmiko_connector_try_ssh_autodetect_success(self, mock_ssh_detect_cls):
        mock_ssh_detect = mock_ssh_detect_cls.return_value
        mock_ssh_detect.autodetect.return_value = 'cisco_ios'
        
        connector = NetmikoConnector()
        result = connector._NetmikoConnector__try_ssh_autodetect(mock_ssh_detect)
        
        self.assertEqual(result, 'cisco_ios')
    
    def test_netmiko_connector_no_username_password(self):
        credentials = {}
        connector = NetmikoConnector()
        
        result = connector.run(self.device, self.geral_commandTest, credentials)
        self.assertEqual(
            result.error,
            'Username and password are required'
        )
        
    @patch('src.connector.netmiko_connector.SNMPDetect', autospec=True)
    @patch('src.connector.netmiko_connector.ConnectHandler')
    #test_3 exceptions by with connect
    def test_netmiko_connector_general_error(self, mock_connect_handler, mock_snmp_detect):
        mock_connect_handler.side_effect = Exception('Test General Error')
        
        connector = NetmikoConnector()
        result = connector.run(self.device, self.geral_commandTest, self.credentials)
        
        self.assertEqual(result.error, 'General error in connecting to device')
        
    @patch('src.connector.netmiko_connector.SNMPDetect', autospec=True)
    @patch('src.connector.netmiko_connector.ConnectHandler')
    #test_3 exceptions by with connect
    def test_netmiko_connector_timeout_error(self, mock_connect_handler, mock_snmp_detect):
        mock_connect_handler.side_effect = NetMikoAuthenticationException
        
        connector = NetmikoConnector()
        result = connector.run(self.device, self.geral_commandTest, self.credentials)
        
        self.assertEqual(result.error, 'Authentication error in connecting to device')
        
    
    @patch('src.connector.netmiko_connector.SNMPDetect', autospec=True)
    @patch('src.connector.netmiko_connector.ConnectHandler')
    #test_3 exceptions by with connect
    def test_netmiko_connector_authentication_error(self, mock_connect_handler, mock_snmp_detect):
        mock_connect_handler.side_effect = NetMikoTimeoutException
        
        connector = NetmikoConnector()
        result = connector.run(self.device, self.geral_commandTest, self.credentials)
        
        self.assertEqual(result.error, 'Timeout in connecting to device')
