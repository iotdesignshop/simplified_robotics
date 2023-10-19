import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from interbotix_xs_msgs.srv import RobotInfo, RegisterValues

CURRENT_UNIT_CONVERSION = 2.69  # Used to convert current units to mA
CURRENT_SAFETY_MARGIN = 0.75 # Current display is reduced by this amount to provide a safety margin prior to fault


class DroNode(Node):
    def __init__(self, robot_info_ui_callback = None, robot_position_ui_callback = None):
        super().__init__('dro_node')
        self.get_logger().info('DRO node started')

        # Mark as not ready
        self.robot_info = None  

        # Check parameter for robot model - default to auto-mate arm
        self.robot_model = self.declare_parameter('robot_model', 'xm540arm').value
        
        # Create service client to get robot info
        self.robot_info_client = self.create_client(RobotInfo, self.robot_model+'/get_robot_info')
        while not self.robot_info_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Robot Info service not available, waiting again...')
        
        # Create service client for getting servo registers
        self.register_values_client = self.create_client(RegisterValues, self.robot_model+'/get_motor_registers')
        while not self.register_values_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Register Values service not available, waiting again...')
        
        # Call service to get robot info
        robot_info_request = RobotInfo.Request()
        robot_info_request.cmd_type = 'group'
        robot_info_request.name = 'arm'    
        self.future = self.robot_info_client.call_async(robot_info_request)
        self.future.add_done_callback(self.robot_info_callback)

        # Call service to get maximum temperatures on servos
        temp_limit_request = RegisterValues.Request()
        temp_limit_request.cmd_type = 'group'
        temp_limit_request.name = 'arm'
        temp_limit_request.reg = 'Temperature_Limit'
        self.future = self.register_values_client.call_async(temp_limit_request)
        self.future.add_done_callback(self.temperature_limit_callback)

        # Call service to get current limit on servos
        current_limit_request = RegisterValues.Request()
        current_limit_request.cmd_type = 'group'
        current_limit_request.name = 'arm'
        current_limit_request.reg = 'Current_Limit'
        self.future = self.register_values_client.call_async(current_limit_request)
        self.future.add_done_callback(self.current_limit_callback)



        # Stash callbacks
        self.robot_info_ui_callback = robot_info_ui_callback
        self.robot_position_ui_callback = robot_position_ui_callback


    def robot_info_callback(self, future):
        try:
            response = future.result()
        except Exception as e:
            self.get_logger().info(
                'Service call failed %r' % (e,))
        else:
            self.get_logger().info('Robot Info: %s' % response)
            self.robot_info = response

        # Notify UI
        if self.robot_info_ui_callback:
            self.robot_info_ui_callback(self.robot_info)
        
        
    def joint_states_callback(self, msg):
        # Notify UI
        if self.robot_position_ui_callback:
            self.robot_position_ui_callback(msg)

    def temperature_limit_callback(self, future):
        try:
            response = future.result()
        except Exception as e:
            self.get_logger().info(
                'Service call failed %r' % (e,))
        else:
            self.get_logger().info('Temperature Limit: %s' % response)
            self.temperature_limit = response
    
    def current_limit_callback(self, future):
        try:
            response = future.result()
        except Exception as e:
            self.get_logger().info(
                'Service call failed %r' % (e,))
        else:
            self.get_logger().info('Current Limit: %s' % response)
            self.current_limit = response.values

            # Multiply the current limits by the conversion factor because the joint state publisher
            # returns values in mA
            for i in range(len(self.current_limit)):
                self.current_limit[i] = int(CURRENT_UNIT_CONVERSION * self.current_limit[i] * CURRENT_SAFETY_MARGIN)

            # Start joint state messages
            self.joint_state_sub = self.create_subscription(
                JointState,
                self.robot_model+'/joint_states',
                self.joint_states_callback,
                10)
            
            



# This class is normally run from the UI, but can be run from the command line
def main(args=None):
    rclpy.init(args=args)
    node = DroNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
