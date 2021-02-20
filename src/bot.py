from rlbot.agents.base_agent import BaseAgent, SimpleControllerState
from rlbot.messages.flat.QuickChatSelection import QuickChatSelection
from rlbot.utils.structures.game_data_struct import GameTickPacket

from util.ball_prediction_analysis import find_slice_at_time
from util.boost_pad_tracker import BoostPadTracker
from util.drive import steer_toward_target
from util.sequence import Sequence, ControlStep
from util.vec import Vec3

import inspect


class MyBot(BaseAgent):

    def __init__(self, name, team, index):
        super().__init__(name, team, index)
        self.active_sequence: Sequence = None
        self.boost_pad_tracker = BoostPadTracker()

    def initialize_agent(self):
        # Set up information about the boost pads now that the game is active and the info is available
        self.boost_pad_tracker.initialize_boosts(self.get_field_info())

    def get_output(self, packet: GameTickPacket) -> SimpleControllerState:
        # print(packet)
        # print(packet.game_info.seconds_elapsed)
        """
        This function will be called by the framework many times per second. This is where you can
        see the motion of the ball, etc. and return controls to drive your car.
        """

        
        ball_location = Vec3(packet.game_ball.physics.location)

        # print(packet.game_info.game_time)
        info = self.get_field_info()
        first_boost_pad = info.boost_pads[1].location

        corner_debug = "Time elapsed: {}\n".format(packet.game_info.seconds_elapsed)
        # print(info.boost_pads[0])
        corner_debug += "First boost location: {}\n".format(first_boost_pad)
        corner_debug += "Ball location: {}\n".format(ball_location)
        # print(self.team)

        # Keep our boost pad info updated with which pads are currently active
        self.boost_pad_tracker.update_boost_status(packet)

        # This is good to keep at the beginning of get_output. It will allow you to continue
        # any sequences that you may have started during a previous call to get_output.
        if self.active_sequence is not None and not self.active_sequence.done:
            controls = self.active_sequence.tick(packet)
            if controls is not None:
                return controls

        # Gather some information about our car and the ball
        my_car = packet.game_cars[self.index]
        car_location = Vec3(my_car.physics.location)
        car_velocity = Vec3(my_car.physics.velocity)

        # By default we will chase the ball, but target_location can be changed later
        # target_location = ball_location
        target_location = Vec3(0, 4240, 0)

        if self.team == 0:
            if ball_location[1] < 0:
                target_location = ball_location
            else:
                target_location = Vec3(0, -4240, 0)

        if self.team == 1:
            if ball_location[1] > 0:
                target_location = ball_location
            else: 
                target_location = Vec3(0, 4240, 0)

        # this means kickoff should be true
        if ball_location.flat() == Vec3(0, 0, 0):
            target_location = Vec3(0,0,0)

        

        if car_location.dist(ball_location) > 1500:
            # We're far away from the ball, let's try to lead it a little bit
            ball_prediction = self.get_ball_prediction_struct()  # This can predict bounces, etc
            ball_in_future = find_slice_at_time(ball_prediction, packet.game_info.seconds_elapsed + 2)
            # print(Vec3(ball_prediction))
            # print(ball_in_future)

            
            # gets ball predictions every 4 slices starting from the 5th slice
            render_ball_predictions = [ball_location]
            for i in range(5, 360, 4):
                render_ball_predictions.append(ball_prediction.slices[i].physics.location)
            # renders the ball predictions
            self.renderer.draw_polyline_3d(render_ball_predictions, self.renderer.blue())


            # ball_in_future might be None if we don't have an adequate ball prediction right now, like during
            # replays, so check it to avoid errors.
            if ball_in_future is not None:
                # target_location = Vec3(ball_in_future.physics.location)
                # target_location = Vec3(0, -4240, 0)
                self.renderer.draw_line_3d(ball_location, target_location, self.renderer.cyan())

        # Draw some things to help understand what the bot is thinking
        self.renderer.draw_line_3d(
            car_location, target_location, self.renderer.white())
        self.renderer.draw_string_3d(
            car_location, 1, 1, f'Speed: {car_velocity.length():.1f}', self.renderer.white())
        self.renderer.draw_rect_3d(
            target_location, 8, 8, True, self.renderer.cyan(), centered=True)

        # print some debug lines in the corner of the screen
        self.renderer.draw_string_2d(20, 20, 1, 1, corner_debug, self.renderer.white())

        if 750 < car_velocity.length() < 800:
            # We'll do a front flip if the car is moving at a certain speed.
            # print(car_velocity)
            return self.begin_front_flip(packet)

        controls = SimpleControllerState()
        controls.steer = steer_toward_target(my_car, target_location)
        controls.throttle = 1
        # You can set more controls if you want, like controls.boost.

        return controls

    def begin_front_flip(self, packet):
        # Send some quickchat just for fun
        # print(car_velocity.length())
        self.send_quick_chat(
            team_only=False, quick_chat=QuickChatSelection.Information_IGotIt)

        # Do a front flip. We will be committed to this for a few seconds and the bot will ignore other
        # logic during that time because we are setting the active_sequence.
        self.active_sequence = Sequence([
            ControlStep(duration=0.05,
                        controls=SimpleControllerState(jump=True)),
            ControlStep(duration=0.05,
                        controls=SimpleControllerState(jump=False)),
            ControlStep(duration=0.2, controls=SimpleControllerState(
                jump=True, pitch=-1)),
            ControlStep(duration=0.8, controls=SimpleControllerState()),
        ])

        # Return the controls associated with the beginning of the sequence so we can start right away.
        return self.active_sequence.tick(packet)
    
    def do_kickoff(self, packet):
        pass
