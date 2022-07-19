#!/usr/bin/env python
import random
import rospy
from std_msgs.msg import String, Header
from std_srvs.srv import Empty
from naoqi_bridge_msgs.msg import JointAnglesWithSpeed, Bumper, HeadTouch
from naoqi import ALProxy
from sensor_msgs.msg import Image, JointState
from cv_bridge import CvBridge, CvBridgeError
import cv2
import numpy as np
import csv
import random
from naoqi import ALProxy
import sys
import RL_DT
from sklearn import tree
import csv
import copy


class tutorial5_soccer:
    def __init__(self, init_state=0, gamma=0.8, MAXSTEPS=100):
        self.blobX = 0
        self.blobY = 0
        self.blobSize = 0
        self.shoulderRoll = 0
        self.shoulderPitch = 0
        # For setting the stiffnes of single joints
        self.jointPub = 0

        self.state = 0 # for RL-DT to read
        self.state_prime = 0 # for RL-DT to read
        self.action = 0 # for RL-DT to read
        self.instant_reward = 0

        # for RL-DT
        self.A = [0, 1, 2]  # 'Left': 0, 'Right': 1, 'Kick': 2
        self.sM = []  # set of all state
        self.visit = np.zeros((10, 3))  # counting the amount of visited state
        self.Q = np.zeros((10, 3))  # q table
        self.Rm = np.zeros((10, 3))  # reward matrix
        self.Ch = False
        self.exp = False
        self.gamma = gamma
        self.maxstep = MAXSTEPS
        self.init_state = init_state
        self.possible_state = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        self.X_train = []
        self.y_train = []
        self.rewardTree = tree.DecisionTreeClassifier()

    # Callback function for reading in the joint values
    def joints_cb(self, data):
        # rospy.loginfo("joint states "+str(data.name)+str(data.position))
        # store current joint information in class variables
        self.joint_names = data.name  # LHipRoll for move in or move out
        self.joint_angles = data.position
        self.joint_velocities = data.velocity

        pass

    # Read in the goal position!
    # TODO: Aruco marker detection
    def image_cb(self, data):
        bridge_instance = CvBridge()

    def set_joint_angles(self, head_angle, topic):
        joint_angles_to_set = JointAnglesWithSpeed()
        joint_angles_to_set.joint_names.append(
            topic)  # each joint has a specific name, look into the joint_state topic or google  # When I
        joint_angles_to_set.joint_angles.append(
            head_angle)  # the joint values have to be in the same order as the names!!
        joint_angles_to_set.relative = False  # if true you can increment positions
        joint_angles_to_set.speed = 0.03  # keep this low if you can
        # print(str(joint_angles_to_set))
        self.jointPub.publish(joint_angles_to_set)

    def set_joint_angles_fast(self, head_angle, topic):
        # fast motion for kick!! careful
        joint_angles_to_set = JointAnglesWithSpeed()
        joint_angles_to_set.joint_names.append(
            topic)  # each joint has a specific name, look into the joint_state topic or google  # When I
        joint_angles_to_set.joint_angles.append(
            head_angle)  # the joint values have to be in the same order as the names!!
        joint_angles_to_set.relative = False  # if true you can increment positions
        joint_angles_to_set.speed = 0.6  # keep this low if you can
        # print(str(joint_angles_to_set))
        self.jointPub.publish(joint_angles_to_set)

    def set_joint_angles_list(self, head_angle_list, topic_list):
        # set the init one stand mode, doing it by all list together
        if len(head_angle_list) == len(topic_list):
            for i in range(len(topic_list)):
                head_angle = head_angle_list[i]
                topic = topic_list[i]
                joint_angles_to_set = JointAnglesWithSpeed()
                joint_angles_to_set.joint_names.append(
                    topic)  # each joint has a specific name, look into the joint_state topic or google  # When I
                joint_angles_to_set.joint_angles.append(
                    head_angle)  # the joint values have to be in the same order as the names!!
                joint_angles_to_set.relative = False  # if true you can increment positions
                joint_angles_to_set.speed = 0.1  # keep this low if you can
                # print(str(joint_angles_to_set))
                self.jointPub.publish(joint_angles_to_set)
                rospy.sleep(0.05)

    def make_action(self, action):
        if action == 0:
            self.move_in()
            rospy.sleep(0.1)
        elif action == 1:
            self.move_out()
            rospy.sleep(0.1)
        else:
            self.kick()
            rospy.sleep(0.1)

    # Moves its left hip back and forward and then goes back into its initial position
    def kick(self):

        self.set_stiffness(True)
        # Move foot back
        self.set_joint_angles(0.48, "LHipPitch")
        rospy.sleep(1.0)
        # fast kick
        self.set_joint_angles_fast(-0.8, "LHipPitch")

        # Move the foot to original position
        rospy.sleep(2.0)
        # self.one_foot_stand()
        self.set_joint_angles(-0.3911280632019043, "LHipPitch")
        self.read_state_joint()

    def set_initial_stand(self):
        robotIP = '10.152.246.137'
        try:
            postureProxy = ALProxy('ALRobotPosture', robotIP, 9559)
        except Exception, e:
            print('could not create ALRobotPosture')
            print('Error was', e)
        postureProxy.goToPosture('Stand', 1.0)
        print(postureProxy.getPostureFamily())

    def one_foot_stand(self):
        # it is the init state ready for kicking
        # careful !!!!!! very easy to fall
        print('one foot mode')
        self.set_stiffness(True)
        # using the rostopic echo to get the desired joint states, not perfect
        # rostopic echo /joint_states
        """
        position_ori = [0.004559993743896484, 0.5141273736953735, 1.8330880403518677, 0.19937801361083984, -1.9574260711669922,
            -1.5124820470809937, -0.8882279396057129, 0.32840001583099365, -0.13955211639404297, 0.31297802925109863,
            -0.3911280632019043, 1.4679961204528809, -0.8943638801574707, -0.12114405632019043, -0.13955211639404297,
            0.3697359561920166, 0.23772811889648438, -0.09232791513204575, 0.07980990409851074, -0.3282339572906494,
            1.676703929901123, -0.45717406272888184, 1.1964781284332275, 0.18872404098510742, 0.36965203285217285, 0.397599995136261]
        """

        # way1 the best position i find
        position = [0.004559993743896484, 0.5141273736953735, 1.8330880403518677, 0.19937801361083984,
                    -1.9574260711669922,
                    -1.5124820470809937, -0.8882279396057129, 0.32840001583099365, -0.13955211639404297, 0.48,
                    -0.3911280632019043, 1.2, -0.4, -0.12114405632019043, -0.13955211639404297,
                    0.3697359561920166, 0.23772811889648438, -0.09232791513204575, 0.07980990409851074,
                    -0.3282339572906494,
                    1.676703929901123, -0.8, 1.1964781284332275, 0.18872404098510742, 0.36965203285217285,
                    0.397599995136261]
        joints = ['HeadYaw', 'HeadPitch', 'LShoulderPitch', 'LShoulderRoll', 'LElbowYaw',
                  'LElbowRoll', 'LWristYaw', 'LHand', 'LHipYawPitch', 'LHipRoll',
                  'LHipPitch', 'LKneePitch', 'LAnklePitch', 'LAnkleRoll', 'RHipYawPitch',
                  'RHipRoll', 'RHipPitch', 'RKneePitch', 'RAnklePitch', 'RAnkleRoll',
                  'RShoulderPitch', 'RShoulderRoll', 'RElbowYaw', 'RElbowRoll', 'RWristYaw', 'RHand']
        '''
        # way 2
        position = [-0.015382051467895508, 0.5120565295219421, 1.8346221446990967, 0.1779019832611084, -1.937483787536621,
                    -1.5124820470809937, -1.0692400932312012, 0.32760000228881836, -0.11807608604431152, 0.31297802925109863,
                    -0.3911280632019043, 1.4664621353149414, -0.8943638801574707, -0.12114405632019043, -0.11807608604431152,
                    0.3697359561920166, 0.2530679702758789, -0.09232791513204575, -0.07665801048278809, -0.269942045211792,
                    1.6951122283935547, -0.4617760181427002, 1.1949440240859985, 0.2025299072265625, 0.3589141368865967, 0.39399999380111694]
        '''
        # backup init position
        # way3 [0.004559993743896484, 0.5141273736953735, 1.8330880403518677, 0.15335798263549805, -1.9129400253295898, -1.5032780170440674, -1.199629783630371, 0.32760000228881836, -0.22852396965026855, 0.4019498825073242, -0.3911280632019043, 1.4679961204528809, -0.8943638801574707, -0.12114405632019043, -0.22852396965026855, 0.3697359561920166, 0.23772811889648438, -0.09232791513204575, 0.08594608306884766, -0.3052239418029785, 1.6905097961425781, -0.44950389862060547, 1.1995460987091064, 0.1994619369506836, 0.3512439727783203, 0.3952000141143799]
        self.set_joint_angles_list(position, joints)

    def move_in(self):
        print('move in')
        self.instant_reward = -1
        if self.state != 0:
            self.state = self.state - 1
            print("dis state:", self.state)
            self.set_joint_LHipRoll(self.state)
        else:
            print("lower bound")

    def move_out(self):
        print('move out')
        self.instant_reward = -1
        if self.state != 9:
            self.state = self.state + 1
            print("dis state:", self.state)
            self.set_joint_LHipRoll(self.state)
        else:
            print("upper bound")

    def set_joint_LHipRoll(self, state):
        joint_angle = 0.48 + state * 0.03
        print('set_angle:', joint_angle)
        self.set_joint_angles(joint_angle, "LHipRoll")
        rospy.sleep(0.5)
        return self.read_state_joint()

    def read_state_joint(self):
        LHipRoll_angle = self.joint_angles[self.joint_names.index('LHipRoll')]
        state_joint = int((LHipRoll_angle - 0.48) / (0.75 - 0.48) * 10)
        print("LHipRoll:", LHipRoll_angle, "state_joint:", state_joint)
        return state_joint


    def set_stiffness(self, value):
        if value == True:
            service_name = '/body_stiffness/enable'
        elif value == False:
            service_name = '/body_stiffness/disable'
        try:
            stiffness_service = rospy.ServiceProxy(service_name, Empty)
            stiffness_service()
        except rospy.ServiceException, e:
            rospy.logerr(e)

    '''
    def touch_cb(self,data):
        if data.button == 1 and data.state == 1:  # TB1
            #self.set_stiffness(True)
            print("Kick motion & stiffness enabled")
            self.kick()
        if data.button == 2 and data.state == 1:
            self.set_stiffness(False)
            print("stiffness should be DISabled")
        if data.button == 3 and data.state == 1:
            self.set_stiffness(True)
            print("stiffness should be ENabled")
        # try kick motion
        #if data.button == 3 and data.state == 1:
        # left knee joint pitch: -0.092346 to 2.112528
        # Left hip joint pitch: -1.535889 to 0.484090
        # for RL motions the left hip roll is important: -0.379472 to 0.790477
    '''

    def touch_cb_reward(self, data):
        if data.button == 1 and data.state == 1:  # miss the goal
            print("miss")
            self.instant_reward = -2
            return self.instant_reward
        if data.button == 2 and data.state == 1:  # goal!!!
            print('goal')
            self.instant_reward = 20
            return self.instant_reward
        if data.button == 3 and data.state == 1:  # fall down
            print('fall down')
            self.instant_reward = -20
            return self.instant_reward
        else:
            self.instant_reward = 0
            return False
        # how to build the waiting signal


    def touch_cb_test(self, data):
        # for test the movement
        if data.button == 1 and data.state == 1:  # TB1
            self.move_in()
        if data.button == 2 and data.state == 1:
            self.move_out()
        if data.button == 3 and data.state == 1:
            print("kick")
            self.kick()

    def tutorial5_soccer_execute_test_by_tactile(self):

        # cmac training here!!!
        rospy.init_node('tutorial5_soccer_node', anonymous=True)
        self.set_stiffness(True)
        self.jointPub = rospy.Publisher("joint_angles", JointAnglesWithSpeed, queue_size=10)

        # self.set_initial_stand()
        rospy.sleep(2.0)
        self.one_foot_stand()
        self.state = 0
        # rospy.Subscriber("joint_states",JointAnglesWithSpeed,self.joints_cb)
        rospy.Subscriber("tactile_touch", HeadTouch, self.touch_cb_test)
        rospy.Subscriber('joint_states', JointState, self.joints_cb)
        # start with setting the initial positions of head and right arm

        # rospy.Subscriber("/nao_robot/camera/top/camera/image_raw", Image, self.image_cb)

        rospy.spin()

    def tutorial5_soccer_test(self):
        rospy.init_node('tutorial5_soccer_node', anonymous=True)
        self.set_stiffness(True)
        self.jointPub = rospy.Publisher("joint_angles", JointAnglesWithSpeed, queue_size=10)
        rospy.sleep(2.0)
        self.one_foot_stand()
        self.state = 0  # init state
        # rospy.Subscriber("joint_states",JointAnglesWithSpeed,self.joints_cb)
        rospy.Subscriber("tactile_touch", HeadTouch, self.touch_cb_test)
        rospy.Subscriber('joint_states', JointState, self.joints_cb)
        # start with setting the initial positions of head and right arm


        # rospy.Subscriber("/nao_robot/camera/top/camera/image_raw", Image, self.image_cb)

        rospy.spin()

    def State_Transition(self, state, action):
        shift = 0
        if action == 0:
            shift = -1
        elif action == 1:
            shift = 1
        next_state = state + shift
        if next_state < 0 or next_state > 9:
            return state
        return next_state


    def get_predictions(self, s_m, a_m):
        r_pred = self.rewardTree.predict([[s_m, a_m]])
        return r_pred[0]


    def add_experience_to_tree(self, s, action, r):
        self.X_train.append([s, action])
        self.y_train.append(r)
        self.rewardTree.fit(self.X_train, self.y_train)
        return True


    def Update_Model(self,s,action,r, s_prime):
        # not completed
        # n = self.state_num
        self.Ch = self.add_experience_to_tree(s, action, r)
        for s_m in self.sM:
            for a_m in self.A:
                # print("pred:", s_m, a_m, self.get_predictions(s_m, a_m))
                self.Rm[s_m][a_m] = self.get_predictions(s_m, a_m)
        return self.Ch
                # self.Rm[s_m][a_m] = self.reward_true[s_m][a_m]


    def Check_Model(self):
        for r in np.nditer(self.Rm):
            if r > 0:
                return True
        return False



    def check_convergence(self, action_values_temp):
        for i in range(self.Q.shape[0]):
            for j in range(self.Q.shape[1]):
                if (abs(self.Q[i][j] - action_values_temp[i][j]) > 0.01):
                    return False
        return True

    def Compute_Value(self, stepsize):
        # Value iteration
        # print("Compute_value")
        minivisits = np.min(self.visit)
        print("visit:", self.visit)
        converged = False
        while not converged:
            Q_temp = copy.deepcopy(self.Q)
            for s in self.sM:
                for a in self.A:
                    if self.exp and self.visit[s][a] == minivisits:
                        print("RMax")
                        self.Q[s][a] = 999
                    else:
                        # print("R")
                        self.Q[s][a] = self.Rm[s][a]
                        s_prime = self.State_Transition(s, a)
                        self.Q[s][a] += self.gamma*max(self.Q[s_prime][:])
            converged = self.check_convergence(Q_temp)

        return 0

    def q_max(self, state):
        Q = self.Q[state][:]
        max_q = Q[0]
        max_i = 0
        for i in range(len(Q)):
            if Q[i] > max_q:
                max_q = Q[i]
                max_i = i
        # print("max_action:", max_i)
        return max_i

    def test(self):
        rospy.init_node('tutorial5_soccer_node', anonymous=True)
        rospy.Subscriber("tactile_touch", HeadTouch, self.touch_cb_reward)  # will give the data?
        print(HeadTouch.state)
        print(HeadTouch.button)
        # rospy.spin()

    def tutorial5_soccer_train(self):
        rospy.init_node('tutorial5_soccer_node', anonymous=True)
        self.set_stiffness(True)
        self.jointPub = rospy.Publisher("joint_angles", JointAnglesWithSpeed, queue_size=10)
        rospy.sleep(2.0)
        self.one_foot_stand()
        # rospy.Subscriber("joint_states",JointAnglesWithSpeed,self.joints_cb)
        rospy.Subscriber("tactile_touch", HeadTouch, self.touch_cb_reward) # will give the data?
        rospy.Subscriber('joint_states', JointState, self.joints_cb)

        # self.state = 0  # init state
        s = self.init_state
        self.sM.append(s)
        converged = False
        while not converged or np.min(self.visit) < 1:
            print(converged)
            Q_temp = copy.deepcopy(self.Q)
            action = self.q_max(s)  # greedy action
            self.make_action(action)
            print("maxaction:", action)
            self.visit[s][action] += 1
            s_prime = self.State_Transition(s, action)
            # r = rl_dt.reward_true[s][action]
            if action == 0 or action == 1:
                r = -1
            else:
                # wait reward signal after kick
                # r = input("reward:")
                """"""
                if s == 0 or s == 9:
                    r = -20
                elif s == 4:
                    r = 20
                else:
                    r = -2

                """
                flag = False
                while not flag:
                    flag = self.touch_cb_reward   # not sure how to read,
                r = flag
                """

            # return reward
            if s_prime not in self.sM:
                self.sM.append(s_prime)

            self.Update_Model(s, action, r, s_prime) # update the reward tree, neglect transition tree
            # self.exp = self.Check_Model()
            self.exp = True
            # print("exp:", self.exp)
            if np.min(self.visit) >= 1:
                self.exp = False
                # stop giving Rmax after every state is visited twice
            if self.Ch:
                # self.Compute_Value(300)
                self.Compute_Value(1000)
            s = s_prime
            print(self.Q)
            converged = self.check_convergence(Q_temp)



if __name__ == '__main__':
    node_instance = tutorial5_soccer()
    # node_instance.one_foot_stand()
    # node_instance.tutorial5_soccer_test()
    # node_instance.tutorial5_soccer_execute_test_by_tactile()
    # node_instance.stand()
    # node_instance.test()
    node_instance.tutorial5_soccer_train()
    # node_instance. tutorial5_soccer_execute_test_by_tactile()


