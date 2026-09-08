#include "prophecy/sim/locomotion.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <utility>

namespace prophecy::sim {
namespace {

constexpr double kPi = 3.1415926535897932384626433832795;
constexpr double kTau = 2.0 * kPi;
constexpr double kDegreesToRadians = kPi / 180.0;
constexpr double kRadiansToDegrees = 180.0 / kPi;

struct SpeedSample {
    double angle;
    double speed;
};

constexpr std::array<SpeedSample, 12> kWalkSpeedSamples{{
    {-180.0 * kDegreesToRadians, 1.5000033307073826},
    {-135.0 * kDegreesToRadians, 1.5000536823014758},
    {-115.0 * kDegreesToRadians, 1.7999555048733633},
    {-90.0 * kDegreesToRadians, 1.8000192001086324},
    {-45.0 * kDegreesToRadians, 2.000104827130553},
    {-20.0 * kDegreesToRadians, 2.000018117805966},
    {0.0, 2.0000178813934326},
    {20.0 * kDegreesToRadians, 2.000018117805966},
    {45.0 * kDegreesToRadians, 2.00001463287474},
    {65.0 * kDegreesToRadians, 1.800019051736406},
    {90.0 * kDegreesToRadians, 1.8000192001086324},
    {135.0 * kDegreesToRadians, 1.5000536823014758},
}};

constexpr std::array<SpeedSample, 12> kRunSpeedSamples{{
    {-180.0 * kDegreesToRadians, 2.9999999256877157},
    {-135.0 * kDegreesToRadians, 3.000001029149122},
    {-110.0 * kDegreesToRadians, 3.4999998734800637},
    {-90.0 * kDegreesToRadians, 3.499999785087478},
    {-45.0 * kDegreesToRadians, 4.999999998722342},
    {-20.0 * kDegreesToRadians, 5.000000553840497},
    {0.0, 5.0},
    {20.0 * kDegreesToRadians, 5.000000553840497},
    {45.0 * kDegreesToRadians, 5.000001077681663},
    {70.0 * kDegreesToRadians, 3.4999998734800637},
    {90.0 * kDegreesToRadians, 3.499999785087478},
    {135.0 * kDegreesToRadians, 2.999999190013914},
}};

struct RunConfig {
    double accel = 8.0;
    double brake = 14.0;
    double lateral = 12.0;
    double reverse = 17.0;
    double yaw_only_accel = 2.87405;
    double yaw_only_brake = 0.14141;
    double yaw_only_direction_deg = 13.13019;
    double yaw_only_yaw_deg = 33.99723;
    double yaw_only_target_speed_max = 3.1062;
    double yaw_only_turn_speed_boost = 3.0;
    double yaw_only_turn_speed_cap = 7.0;
    double side90_accel = 13.52188;
    double side90_brake = 25.3446;
    double side90_lateral = 10.97483;
    double side90_reverse = 27.03166;
    double side90_front_cross_target_speed_min = 4.89515;
    double side90_front_cross_forward_deg = 71.34982;
    double side90_front_cross_accel = 19.67657;
    double side90_front_cross_brake = 28.46706;
    double side90_front_cross_lateral = 14.93534;
    double side90_front_cross_reverse = 16.73861;
    double side90_front_to_side_current_speed_min = 4.0;
    double side90_front_to_side_target_speed_min = 3.2;
    double side90_front_to_side_target_speed_max = 3.8;
    double side90_front_to_side_current_deg = 35.0;
    double side90_front_to_side_target_deg = 20.0;
    double side90_front_to_side_accel = 7.79785;
    double side90_front_to_side_brake = 26.47702;
    double side90_front_to_side_lateral = 15.59431;
    double side90_front_to_side_reverse = 14.11128;
    double side135_accel = 19.68464;
    double side135_brake = 13.43519;
    double side135_lateral = 3.52658;
    double side135_reverse = 17.28826;
    double side135_front_to_side_speed_min = 2.81293;
    double side135_front_to_side_speed_max = 3.78281;
    double side135_front_to_side_current_deg = 73.19556;
    double side135_front_to_side_target_deg = 28.91449;
    double side135_front_to_side_accel = 28.82969;
    double side135_front_to_side_brake = 16.61154;
    double side135_front_to_side_lateral = 5.99996;
    double side135_front_to_side_reverse = 18.27166;
    double side135_back_to_front_speed_min = 3.07996;
    double side135_back_to_front_speed_max = 5.36388;
    double side135_back_to_front_current_deg = 118.96187;
    double side135_back_to_front_target_deg = 57.20270;
    double side135_back_to_front_accel = 11.09099;
    double side135_back_to_front_brake = 21.69045;
    double side135_back_to_front_lateral = 3.75640;
    double side135_back_to_front_reverse = 13.10702;
    double side135_back_to_side_speed_min = 2.92332;
    double side135_back_to_side_speed_max = 4.15660;
    double side135_back_to_side_current_deg = 113.69210;
    double side135_back_to_side_target_deg = 18.06715;
    double side135_back_to_side_accel = 33.31245;
    double side135_back_to_side_brake = 22.19563;
    double side135_back_to_side_lateral = 2.35843;
    double side135_back_to_side_reverse = 11.54950;
    double side135_front_to_back_current_speed_min = 4.63140;
    double side135_front_to_back_speed_min = 2.2;
    double side135_front_to_back_speed_max = 3.4;
    double side135_front_to_back_current_deg = 55.0;
    double side135_front_to_back_target_deg = 113.94009;
    double side135_front_to_back_accel = 26.91419;
    double side135_front_to_back_brake = 26.15889;
    double side135_front_to_back_lateral = 18.81978;
    double side135_front_to_back_reverse = 25.55118;
    double side135_slow_accel = 17.49487;
    double side135_slow_brake = 2.66471;
    double side135_slow_lateral = 6.56703;
    double side135_slow_reverse = 22.85027;
    double side135_slow_target_speed = 2.93906;
    double pivot_accel = 13.71576;
    double pivot_brake = 29.67206;
    double pivot_lateral = 32.38897;
    double pivot_reverse = 14.10811;
    double pivot_slow_accel = 6.27978;
    double pivot_slow_brake = 32.77245;
    double pivot_slow_lateral = 7.71782;
    double pivot_slow_reverse = 19.74114;
    double pivot_slow_target_speed = 3.21050;
    double side_yaw_deg = 12.2463;
    double side_direction_deg = 50.3356;
    double side135_direction_deg = 113.1491;
    double pivot_direction_deg = 160.8244;
    double turn45_accel = 8.91317;
    double turn45_brake = 19.45370;
    double turn45_lateral = 34.48005;
    double turn45_reverse = 5.01163;
    double turn45_yaw_deg = 41.37735;
    double turn45_direction_deg = 41.26830;
    double turn45_target_speed_min = 4.29293;
    double turn45_max_direction_deg = 51.62113;
    double turn45_max_yaw_deg = 59.93355;
    double turn45_yaw_rate_max_deg_s = 154.81691;
    double turn45_yaw_coupling = -1.49791;
    double stop_accel = 18.3823;
    double stop_brake = 18.0;
    double stop_lateral = 28.3411;
    double stop_reverse = 18.7495;
    double stop_target_speed = 0.9819;
    double stop_initial_speed = 2.0161;
    double stop_forward_brake = 21.0;
    double stop_diagonal_brake = 34.0;
    double stop_other_brake = 18.0;
    double stop_forward_deg = 30.0;
    double stop_diagonal_deg = 80.0;
    double turn_accel = 18.79119;
    double turn_brake = 14.66354;
    double turn_lateral = 13.56151;
    double turn_reverse = 15.65493;
    double turn_yaw_deg = 69.84543;
    double turn_direction_deg = 64.21185;
    double turn_target_speed_min = 4.52071;
    double turn135_direction_deg = 115.0;
    double turn180_direction_deg = 150.0;
    double turn_yaw_coupling = -0.25;
    double fast_turn135_current_speed_min = 5.25;
    double fast_turn135_target_speed_min = 4.6;
    double fast_turn135_accel = 31.26237;
    double fast_turn135_brake = 62.89521;
    double fast_turn135_lateral = 62.27150;
    double fast_turn135_reverse = 5.05603;
    double fast_turn180_current_speed_min = 4.75;
    double fast_turn180_target_speed_min = 4.75;
    double fast_turn180_accel = 39.72145;
    double fast_turn180_brake = 37.57581;
    double fast_turn180_lateral = 36.11129;
    double fast_turn180_reverse = 21.39129;
};

constexpr RunConfig kRun{};
constexpr double kWalkAccelBase = 7.0;
constexpr double kWalkAccelErrorGain = 0.5;
constexpr double kWalkStopBrake = 18.0;
constexpr double kYawMotorAccelDegS2 = 1200.0;
constexpr double kYawMotorBrakeDegS2 = 900.0;
constexpr double kYawMotorMaxRateDeg = 320.0;

double WrapAngle(double angle) noexcept {
    double wrapped = std::fmod(angle + kPi, kTau);
    if (wrapped < 0.0) wrapped += kTau;
    return wrapped - kPi;
}

double Length(Vec2 value) noexcept { return std::hypot(value.x, value.z); }
Vec2 Add(Vec2 a, Vec2 b) noexcept { return {a.x + b.x, a.z + b.z}; }
Vec2 Subtract(Vec2 a, Vec2 b) noexcept { return {a.x - b.x, a.z - b.z}; }
Vec2 Scale(Vec2 value, double scale) noexcept { return {value.x * scale, value.z * scale}; }
double Dot(Vec2 a, Vec2 b) noexcept { return a.x * b.x + a.z * b.z; }

Vec2 MoveToward(Vec2 current, Vec2 target, double maximum_delta) noexcept {
    const Vec2 delta = Subtract(target, current);
    const double distance = Length(delta);
    if (distance <= maximum_delta || distance < 1.0e-8) return target;
    return Add(current, Scale(delta, maximum_delta / distance));
}

double MoveToward(double current, double target, double maximum_delta) noexcept {
    const double delta = target - current;
    if (std::abs(delta) <= maximum_delta) return target;
    return current + std::copysign(maximum_delta, delta);
}

Vec2 Rotate(Vec2 value, double angle) noexcept {
    const double cosine = std::cos(angle);
    const double sine = std::sin(angle);
    return {cosine * value.x + sine * value.z, -sine * value.x + cosine * value.z};
}

double MoveYawMotor(double previous, double current, double target,
    double preferred_delta, double dt, bool allow_momentum) noexcept {
    const double error = SignedAngleDelta(current, target, preferred_delta);
    if (!allow_momentum && std::abs(error) < 1.0e-10) return target;
    const double current_rate = SignedAngleDelta(previous, current) / std::max(1.0e-8, dt);
    // Settle only when the remaining motion can be stopped within this step.
    // Without this, a discrete acceleration-limited motor limit-cycles around
    // zero error; unlike the legacy unconditional clamp, large impulses survive.
    const double stop_rate = kYawMotorBrakeDegS2 * kDegreesToRadians * dt;
    if (allow_momentum && std::abs(current_rate) <= stop_rate &&
        std::abs(error) <= 0.5 * stop_rate * dt) return target;
    const double sign = error >= 0.0 ? 1.0 : -1.0;
    const double desired_rate_abs_deg = std::min(kYawMotorMaxRateDeg,
        std::sqrt(std::max(0.0, 2.0 * (kYawMotorBrakeDegS2 * kDegreesToRadians) * std::abs(error))) * kRadiansToDegrees);
    const double desired_rate = desired_rate_abs_deg * kDegreesToRadians * sign;
    const double current_rate_along_deg = current_rate * kRadiansToDegrees * sign;
    const double rate_limit = current_rate_along_deg > desired_rate_abs_deg
        ? kYawMotorBrakeDegS2 : kYawMotorAccelDegS2;
    const double new_rate = MoveToward(current_rate, desired_rate, rate_limit * kDegreesToRadians * dt);
    double step = new_rate * dt;
    if (!allow_momentum && std::abs(step) > std::abs(error)) step = error;
    return current + step;
}

double DirectionDegrees(Vec2 value) noexcept {
    return std::atan2(value.x, value.z) * kRadiansToDegrees;
}

struct Rates { double accel; double brake; double lateral; double reverse; };

Rates LiveSectorRates(Vec2 current, Vec2 target, LocomotionResponse response, Rates fallback) noexcept {
    const double current_speed = Length(current);
    const double target_speed = Length(target);
    if (response == LocomotionResponse::Side135 && current_speed >= kRun.fast_turn135_current_speed_min &&
        target_speed >= kRun.fast_turn135_target_speed_min) {
        return {kRun.fast_turn135_accel, kRun.fast_turn135_brake,
            kRun.fast_turn135_lateral, kRun.fast_turn135_reverse};
    }
    if ((response == LocomotionResponse::Pivot || response == LocomotionResponse::Turn180) &&
        current_speed >= kRun.fast_turn180_current_speed_min && target_speed >= kRun.fast_turn180_target_speed_min) {
        return {kRun.fast_turn180_accel, kRun.fast_turn180_brake,
            kRun.fast_turn180_lateral, kRun.fast_turn180_reverse};
    }
    if (response != LocomotionResponse::Side90 && response != LocomotionResponse::Side135 &&
        response != LocomotionResponse::Side135Slow) return fallback;
    if (current_speed < 1.0e-5 || target_speed < 1.0e-5) return fallback;

    const double current_deg = std::abs(DirectionDegrees(current));
    const double target_deg = std::abs(DirectionDegrees(target));
    const double target_side_deg = std::abs(target_deg - 90.0);
    if (response == LocomotionResponse::Side90 && target_speed > kRun.side90_front_cross_target_speed_min &&
        current_deg < kRun.side90_front_cross_forward_deg && target_deg < kRun.side90_front_cross_forward_deg &&
        current.x * target.x < 0.0) {
        return {kRun.side90_front_cross_accel, kRun.side90_front_cross_brake,
            kRun.side90_front_cross_lateral, kRun.side90_front_cross_reverse};
    }
    if (response == LocomotionResponse::Side90 && current_speed > kRun.side90_front_to_side_current_speed_min &&
        target_speed > kRun.side90_front_to_side_target_speed_min &&
        target_speed < kRun.side90_front_to_side_target_speed_max &&
        current_deg < kRun.side90_front_to_side_current_deg && target_side_deg < kRun.side90_front_to_side_target_deg) {
        return {kRun.side90_front_to_side_accel, kRun.side90_front_to_side_brake,
            kRun.side90_front_to_side_lateral, kRun.side90_front_to_side_reverse};
    }
    if (response == LocomotionResponse::Side135 || response == LocomotionResponse::Side135Slow) {
        if (target_speed >= kRun.side135_front_to_side_speed_min && target_speed <= kRun.side135_front_to_side_speed_max &&
            current_deg < kRun.side135_front_to_side_current_deg && target_side_deg < kRun.side135_front_to_side_target_deg) {
            return {kRun.side135_front_to_side_accel, kRun.side135_front_to_side_brake,
                kRun.side135_front_to_side_lateral, kRun.side135_front_to_side_reverse};
        }
        if (target_speed >= kRun.side135_back_to_front_speed_min && target_speed <= kRun.side135_back_to_front_speed_max &&
            current_deg > kRun.side135_back_to_front_current_deg && target_deg < kRun.side135_back_to_front_target_deg) {
            return {kRun.side135_back_to_front_accel, kRun.side135_back_to_front_brake,
                kRun.side135_back_to_front_lateral, kRun.side135_back_to_front_reverse};
        }
        if (target_speed >= kRun.side135_back_to_side_speed_min && target_speed <= kRun.side135_back_to_side_speed_max &&
            current_deg > kRun.side135_back_to_side_current_deg && target_side_deg < kRun.side135_back_to_side_target_deg &&
            current.x * target.x < 0.0) {
            return {kRun.side135_back_to_side_accel, kRun.side135_back_to_side_brake,
                kRun.side135_back_to_side_lateral, kRun.side135_back_to_side_reverse};
        }
        if (current_speed > kRun.side135_front_to_back_current_speed_min &&
            target_speed >= kRun.side135_front_to_back_speed_min && target_speed <= kRun.side135_front_to_back_speed_max &&
            current_deg < kRun.side135_front_to_back_current_deg && target_deg > kRun.side135_front_to_back_target_deg) {
            return {kRun.side135_front_to_back_accel, kRun.side135_front_to_back_brake,
                kRun.side135_front_to_back_lateral, kRun.side135_front_to_back_reverse};
        }
    }
    return fallback;
}

Rates ResponseRates(LocomotionResponse response) noexcept {
    switch (response) {
        case LocomotionResponse::YawOnly: return {kRun.yaw_only_accel, kRun.yaw_only_brake, kRun.lateral, kRun.reverse};
        case LocomotionResponse::Side90: return {kRun.side90_accel, kRun.side90_brake, kRun.side90_lateral, kRun.side90_reverse};
        case LocomotionResponse::Side135: return {kRun.side135_accel, kRun.side135_brake, kRun.side135_lateral, kRun.side135_reverse};
        case LocomotionResponse::Side135Slow: return {kRun.side135_slow_accel, kRun.side135_slow_brake, kRun.side135_slow_lateral, kRun.side135_slow_reverse};
        case LocomotionResponse::Pivot: return {kRun.pivot_accel, kRun.pivot_brake, kRun.pivot_lateral, kRun.pivot_reverse};
        case LocomotionResponse::PivotSlow: return {kRun.pivot_slow_accel, kRun.pivot_slow_brake, kRun.pivot_slow_lateral, kRun.pivot_slow_reverse};
        case LocomotionResponse::Stop: return {kRun.stop_accel, kRun.stop_brake, kRun.stop_lateral, kRun.stop_reverse};
        case LocomotionResponse::Turn45: return {kRun.turn45_accel, kRun.turn45_brake, kRun.turn45_lateral, kRun.turn45_reverse};
        case LocomotionResponse::Turn90:
        case LocomotionResponse::Turn135:
        case LocomotionResponse::Turn180: return {kRun.turn_accel, kRun.turn_brake, kRun.turn_lateral, kRun.turn_reverse};
        case LocomotionResponse::Normal: break;
    }
    return {kRun.accel, kRun.brake, kRun.lateral, kRun.reverse};
}

Vec2 MoveRunVelocity(Vec2 current, Vec2 target, double dt, LocomotionResponse response) noexcept {
    Rates rates = LiveSectorRates(current, target, response, ResponseRates(response));
    const double target_speed = Length(target);
    const double current_speed = Length(current);
    if (response == LocomotionResponse::Stop && target_speed < 1.0e-8 && current_speed > 1.0e-6) {
        const double direction = std::abs(DirectionDegrees(current));
        rates.brake = direction < kRun.stop_forward_deg ? kRun.stop_forward_brake
            : direction < kRun.stop_diagonal_deg ? kRun.stop_diagonal_brake : kRun.stop_other_brake;
    }
    if (target_speed < 1.0e-8) return MoveToward(current, {}, rates.brake * dt);
    const Vec2 target_direction = Scale(target, 1.0 / target_speed);
    double parallel = Dot(current, target_direction);
    Vec2 lateral = Subtract(current, Scale(target_direction, parallel));
    const double parallel_rate = parallel < 0.0 ? rates.reverse
        : target_speed < parallel ? rates.brake : rates.accel;
    parallel = MoveToward(parallel, target_speed, parallel_rate * dt);
    lateral = MoveToward(lateral, {}, rates.lateral * dt);
    return Add(Scale(target_direction, parallel), lateral);
}

LocomotionResponse ClassifyRunResponse(const LocomotionState& state, Vec2 target_velocity,
    double target_yaw, double yaw_error, double dt) noexcept {
    const double target_speed = Length(target_velocity);
    const double state_speed = Length(state.velocity);
    LocomotionResponse response = LocomotionResponse::Normal;
    if (target_speed > 1.0e-6 && state_speed > 1.0e-6) {
        const double direction_error = WrapAngle(std::atan2(target_velocity.x, target_velocity.z) -
            std::atan2(state.velocity.x, state.velocity.z));
        const double direction_deg = std::abs(direction_error * kRadiansToDegrees);
        const double yaw_deg = std::abs(yaw_error * kRadiansToDegrees);
        const double yaw_step = SignedAngleDelta(state.previous_yaw_radians, state.yaw_radians);
        const double yaw_rate_deg_s = std::abs(yaw_step * kRadiansToDegrees) / std::max(1.0e-8, dt);
        if (direction_deg < kRun.yaw_only_direction_deg && yaw_deg > kRun.yaw_only_yaw_deg &&
            target_speed < kRun.yaw_only_target_speed_max) response = LocomotionResponse::YawOnly;
        else if (yaw_deg < kRun.side_yaw_deg && direction_deg > kRun.side_direction_deg) {
            if (direction_deg > kRun.pivot_direction_deg) response = target_speed < kRun.pivot_slow_target_speed
                ? LocomotionResponse::PivotSlow : LocomotionResponse::Pivot;
            else if (direction_deg > kRun.side135_direction_deg) response = target_speed < kRun.side135_slow_target_speed
                ? LocomotionResponse::Side135Slow : LocomotionResponse::Side135;
            else response = LocomotionResponse::Side90;
        } else if (direction_error * yaw_error > 0.0 && yaw_deg > kRun.turn45_yaw_deg &&
            direction_deg > kRun.turn45_direction_deg && target_speed > kRun.turn45_target_speed_min &&
            direction_deg < kRun.turn45_max_direction_deg && yaw_deg < kRun.turn45_max_yaw_deg &&
            yaw_rate_deg_s < kRun.turn45_yaw_rate_max_deg_s) response = LocomotionResponse::Turn45;
        else if (direction_error * yaw_error > 0.0 && yaw_deg > kRun.turn_yaw_deg &&
            direction_deg > kRun.turn_direction_deg && target_speed > kRun.turn_target_speed_min) {
            response = direction_deg > kRun.turn180_direction_deg ? LocomotionResponse::Turn180
                : direction_deg > kRun.turn135_direction_deg ? LocomotionResponse::Turn135
                : LocomotionResponse::Turn90;
        }
    }
    if (response == LocomotionResponse::Normal && target_speed < kRun.stop_target_speed &&
        state_speed > kRun.stop_initial_speed) response = LocomotionResponse::Stop;
    (void)target_yaw;
    return response;
}

template <std::size_t N>
double CircularSpeed(const std::array<SpeedSample, N>& samples, double direction) noexcept {
    double angle = WrapAngle(direction);
    if (angle < samples.front().angle) angle += kTau;
    for (std::size_t index = 0; index < samples.size(); ++index) {
        const SpeedSample& first = samples[index];
        const SpeedSample& second = index + 1U < samples.size()
            ? samples[index + 1U] : samples.front();
        const double second_angle = index + 1U < samples.size() ? second.angle : second.angle + kTau;
        if (angle >= first.angle && angle <= second_angle) {
            const double span = second_angle - first.angle;
            const double t = std::abs(span) < 1.0e-8 ? 0.0 : (angle - first.angle) / span;
            return first.speed * (1.0 - t) + second.speed * t;
        }
    }
    return samples.front().speed;
}

}  // namespace

double SignedAngleDelta(double start, double end, double preferred) noexcept {
    const double delta = WrapAngle(end - start);
    if (std::abs(std::abs(delta) - kPi) < 1.0e-4 && std::abs(preferred) > 1.0e-4) {
        return std::copysign(kPi, preferred);
    }
    return delta;
}

Vec2 DirectionFromAngle(double angle) noexcept {
    return {std::sin(angle), std::cos(angle)};
}

double DirectionalSpeedCap(LocomotionMode mode, double root_relative_direction_radians) noexcept {
    return mode != LocomotionMode::Run
        ? CircularSpeed(kWalkSpeedSamples, root_relative_direction_radians)
        : CircularSpeed(kRunSpeedSamples, root_relative_direction_radians);
}

void StepLocomotion(LocomotionState& state, const LocomotionIntent& intent, double dt) noexcept {
    StepLocomotion(state, intent, dt, nullptr);
}

void StepLocomotion(LocomotionState& state, const LocomotionIntent& intent, double dt,
    LocomotionTarget* out_target, bool allow_yaw_momentum) noexcept {
    if (dt <= 0.0) return;
    const double amplitude = std::clamp(intent.speed_amplitude, 0.0, 1.0);
    const double speed_scale = std::clamp(intent.speed_scale, 0.0, 1.0);
    const double turn_scale = std::clamp(intent.turn_scale, 0.0, 1.0);
    const double target_speed = amplitude * speed_scale *
        DirectionalSpeedCap(intent.mode, intent.speed_direction_radians);
    const double world_direction = state.yaw_radians + intent.speed_direction_radians;
    Vec2 target_velocity = Scale(DirectionFromAngle(world_direction), target_speed);
    const double preferred_yaw = SignedAngleDelta(state.yaw_radians, intent.orientation_yaw_radians);
    const double yaw_error = SignedAngleDelta(state.yaw_radians, intent.orientation_yaw_radians, preferred_yaw);
    const double full_speed_yaw = MoveYawMotor(state.previous_yaw_radians, state.yaw_radians,
        intent.orientation_yaw_radians, preferred_yaw, dt, allow_yaw_momentum);
    // External angular momentum is not a steering command. Zero turn strength
    // removes the motor's correction, not the already imparted angular velocity.
    const double inertial_yaw = allow_yaw_momentum
        ? state.yaw_radians + SignedAngleDelta(state.previous_yaw_radians, state.yaw_radians)
        : state.yaw_radians;
    const double new_yaw = inertial_yaw + turn_scale *
        SignedAngleDelta(inertial_yaw, full_speed_yaw, preferred_yaw);

    LocomotionResponse response = LocomotionResponse::Normal;
    if (intent.mode == LocomotionMode::Run) {
        response = ClassifyRunResponse(state, target_velocity, intent.orientation_yaw_radians, yaw_error, dt);
        if (response == LocomotionResponse::Turn45 || response == LocomotionResponse::Turn90 ||
            response == LocomotionResponse::Turn135 || response == LocomotionResponse::Turn180) {
            const double coupling = response == LocomotionResponse::Turn45
                ? kRun.turn45_yaw_coupling : kRun.turn_yaw_coupling;
            if (std::abs(coupling) > 1.0e-8) state.velocity = Rotate(state.velocity,
                (new_yaw - state.yaw_radians) * coupling);
        }
        if (response == LocomotionResponse::YawOnly && target_speed > 1.0e-6) {
            const double yaw_fraction = std::min(1.0, std::abs(yaw_error * kRadiansToDegrees) / 180.0);
            const double boosted_speed = std::min(kRun.yaw_only_turn_speed_cap,
                target_speed + kRun.yaw_only_turn_speed_boost * yaw_fraction);
            if (boosted_speed > target_speed) target_velocity = Scale(target_velocity, boosted_speed / target_speed);
        }
        state.velocity = MoveRunVelocity(state.velocity, target_velocity, dt, response);
    } else {
        if (target_speed < 1.0e-8 && Length(state.velocity) > 1.0e-6) {
            response = LocomotionResponse::Stop;
            state.velocity = MoveToward(state.velocity, {}, kWalkStopBrake * dt);
        } else {
            const double maximum_accel = kWalkAccelBase + kWalkAccelErrorGain * Length(Subtract(target_velocity, state.velocity));
            state.velocity = MoveToward(state.velocity, target_velocity, maximum_accel * dt);
        }
    }

    if (out_target) {
        out_target->velocity = target_velocity;
        out_target->orientation_yaw_radians = intent.orientation_yaw_radians;
    }

    const Vec2 displacement = Scale(state.velocity, dt);
    state.position = Add(state.position, displacement);
    state.distance_travelled += Length(displacement);
    state.previous_yaw_radians = state.yaw_radians;
    state.yaw_radians = new_yaw;
    state.response = response;
}

FutureRootWindow PredictFutureRoots(const LocomotionState& state,
    const LocomotionIntent& intent, double dt, bool allow_yaw_momentum) noexcept {
    FutureRootWindow future{};
    LocomotionState projected = state;
    for (RootTransform& root : future) {
        StepLocomotion(projected, intent, dt, nullptr, allow_yaw_momentum);
        root.position = projected.position;
        root.yaw_radians = projected.yaw_radians;
    }
    return future;
}

const char* ToString(LocomotionMode mode) noexcept {
    if (mode == LocomotionMode::Run) return "Run";
    if (mode == LocomotionMode::Crawl) return "Crawl";
    return "Walk";
}

const char* ToString(LocomotionResponse response) noexcept {
    switch (response) {
        case LocomotionResponse::Normal: return "normal";
        case LocomotionResponse::Stop: return "stop";
        case LocomotionResponse::YawOnly: return "yaw_only";
        case LocomotionResponse::Side90: return "side90";
        case LocomotionResponse::Side135: return "side135";
        case LocomotionResponse::Side135Slow: return "side135_slow";
        case LocomotionResponse::Pivot: return "pivot";
        case LocomotionResponse::PivotSlow: return "pivot_slow";
        case LocomotionResponse::Turn45: return "turn45";
        case LocomotionResponse::Turn90: return "turn90";
        case LocomotionResponse::Turn135: return "turn135";
        case LocomotionResponse::Turn180: return "turn180";
    }
    return "normal";
}

}  // namespace prophecy::sim
