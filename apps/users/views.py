import pyotp
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from django.conf import settings
from apps.users.models import User, PatientProfile
from apps.users.serializers import (
    UserRegistrationSerializer,
    UserDetailSerializer,
    LoginSerializer,
    MFAVerifySerializer,
    PatientProfileSerializer,
)

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    refresh['email'] = user.email
    refresh['role'] = user.role
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

class RegisterView(APIView):
    """
    Register a new user (Patient, Doctor, Admin).
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Authentication & Users'],
        request=UserRegistrationSerializer,
        responses={201: UserDetailSerializer}
    )
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            tokens = get_tokens_for_user(user)
            return Response({
                'success': True,
                'message': 'User registered successfully.',
                'user': UserDetailSerializer(user).data,
                'tokens': tokens
            }, status=status.HTTP_201_CREATED)
        return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    Authenticates user with email and password.
    Returns JWT tokens or temporary token if MFA challenge is required.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Authentication & Users'],
        request=LoginSerializer,
        responses={
            200: inline_serializer(
                name='LoginResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'mfa_required': serializers.BooleanField(),
                    'tokens': serializers.DictField(required=False),
                    'temp_token': serializers.CharField(required=False),
                    'user': UserDetailSerializer(required=False)
                }
            )
        }
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email'].lower()
        password = serializer.validated_data['password']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'success': False, 'message': 'Invalid email or password.'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):
            return Response({'success': False, 'message': 'Invalid email or password.'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({'success': False, 'message': 'Account is inactive.'}, status=status.HTTP_403_FORBIDDEN)

        if user.mfa_enabled and user.mfa_secret:
            refresh = RefreshToken.for_user(user)
            refresh['mfa_pending'] = True
            return Response({
                'success': True,
                'mfa_required': True,
                'temp_token': str(refresh.access_token),
                'message': 'MFA is enabled. Please submit 6-digit TOTP token to verify.'
            }, status=status.HTTP_200_OK)

        tokens = get_tokens_for_user(user)
        return Response({
            'success': True,
            'mfa_required': False,
            'tokens': tokens,
            'user': UserDetailSerializer(user).data
        }, status=status.HTTP_200_OK)


class MFASetupView(APIView):
    """
    Generates TOTP secret and QR provisioning URI for Google Authenticator.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Authentication & Users'],
        request=None,
        responses={
            200: inline_serializer(
                name='MFASetupResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'secret': serializers.CharField(),
                    'provisioning_uri': serializers.CharField(),
                    'instructions': serializers.CharField(),
                }
            )
        }
    )
    def post(self, request):
        user = request.user
        secret = pyotp.random_base32()
        user.mfa_secret = secret
        user.save(update_fields=['mfa_secret'])

        totp = pyotp.TOTP(secret)
        issuer = getattr(settings, 'MFA_ISSUER', 'AmrutamAyurveda')
        provisioning_uri = totp.provisioning_uri(name=user.email, issuer_name=issuer)

        return Response({
            'success': True,
            'secret': secret,
            'provisioning_uri': provisioning_uri,
            'instructions': 'Scan the QR code or enter secret into your authenticator app, then verify with OTP.'
        })


class MFAVerifyView(APIView):
    """
    Verifies 6-digit TOTP token to complete MFA activation or MFA login.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Authentication & Users'],
        request=MFAVerifySerializer,
        responses={
            200: inline_serializer(
                name='MFAVerifyResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'message': serializers.CharField(),
                    'tokens': serializers.DictField(required=False),
                }
            )
        }
    )
    def post(self, request):
        serializer = MFAVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        otp = serializer.validated_data['otp']
        temp_token = serializer.validated_data.get('temp_token')

        if request.user and request.user.is_authenticated:
            user = request.user
            if not user.mfa_secret:
                return Response({'success': False, 'message': 'Call MFA setup first.'}, status=status.HTTP_400_BAD_REQUEST)
            totp = pyotp.TOTP(user.mfa_secret)
            if totp.verify(otp):
                user.mfa_enabled = True
                user.save(update_fields=['mfa_enabled'])
                return Response({'success': True, 'message': 'MFA successfully enabled.'})
            return Response({'success': False, 'message': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        if temp_token:
            try:
                from rest_framework_simplejwt.tokens import AccessToken
                token = AccessToken(temp_token)
                user_id = token['user_id']
                user = User.objects.get(id=user_id)
            except Exception:
                return Response({'success': False, 'message': 'Invalid or expired temporary token.'}, status=status.HTTP_401_UNAUTHORIZED)

            if not user.mfa_secret:
                return Response({'success': False, 'message': 'MFA is not configured.'}, status=status.HTTP_400_BAD_REQUEST)

            totp = pyotp.TOTP(user.mfa_secret)
            if totp.verify(otp):
                tokens = get_tokens_for_user(user)
                return Response({
                    'success': True,
                    'tokens': tokens,
                    'user': UserDetailSerializer(user).data
                })
            return Response({'success': False, 'message': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': False, 'message': 'Authentication or temp_token required.'}, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    """
    Retrieve and update authenticated user details and profile.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Authentication & Users'],
        responses={200: UserDetailSerializer}
    )
    def get(self, request):
        return Response({
            'success': True,
            'user': UserDetailSerializer(request.user).data
        })

    @extend_schema(
        tags=['Authentication & Users'],
        request=UserDetailSerializer,
        responses={200: UserDetailSerializer}
    )
    def patch(self, request):
        user = request.user
        user_data = {k: v for k, v in request.data.items() if k in ['first_name', 'last_name', 'phone_number']}
        for k, v in user_data.items():
            setattr(user, k, v)
        user.save()

        profile_data = request.data.get('patient_profile')
        if profile_data and hasattr(user, 'patient_profile'):
            profile = user.patient_profile
            for k in ['date_of_birth', 'gender', 'blood_group', 'emergency_contact', 'allergies', 'chronic_conditions', 'prakriti']:
                if k in profile_data:
                    setattr(profile, k, profile_data[k])
            profile.save()

        return Response({
            'success': True,
            'message': 'Profile updated successfully.',
            'user': UserDetailSerializer(user).data
        })
