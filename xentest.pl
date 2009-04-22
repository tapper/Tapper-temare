#!/usr/bin/env perl

use strict;
use warnings;
use File::Stat qw(:all);
use File::Basename;
use YAML::Syck;

my $kernel_path = "/data/bancroft/artemis/live/repository/packages/kernel/";


our $temarepath="/home/artemis/temare";
$ENV{PYTHONPATH}=$ENV{PYTHONPATH}.":$temarepath/src";
our $artemispath="/home/artemis/perl510/";
our $execpath="$artemispath/bin";
our $grub_precondition=14;
our %hostliste = ("athene" => 1,
                  "kobold" => 1,
                  "satyr"  => 1,
                  "lemure" => 1);
our $filename="/tmp/temare.yml";


sub gen_xen
{
        my ($host) = @_;
        my $yaml   = qx($temarepath/temare subjectprep $host);
        return if $?;
        my $config = Load($yaml);
        
        open (FH,">",$filename) or die "Can't open $filename:$!";
        print FH $yaml;
        close FH or die "Can't write $filename:$!";
        open(FH, "$execpath/artemis-testrun newprecondition --condition_file=$filename|") or die "Can't open pipe:$!";
        my $precond_id = <FH>;
        chomp $precond_id;

        my $testrun;
        if ($config->{name} eq "automatically generated KVM test") {
                $testrun    = qx($execpath/artemis-testrun new --topic=KVM --precondition=$precond_id --host=$host);
                print "KVM on $host with precondition $precond_id: $testrun";
        } else {
                $testrun    = qx($execpath/artemis-testrun new --topic=Xen --precondition=$grub_precondition --precondition=$precond_id --host=$host);
                print "Xen on $host with preconditions $grub_precondition, $precond_id: $testrun";
        }
}


sub younger
{
        my $st_a = stat($a);
        my $st_b = stat($b);
        return $st_a->mtime() <=> $st_b->mtime();
}

sub gen_kernel
{
        my ($host)          =  @_;
        my @kernelfiles     =  sort younger <$kernel_path/x86_64/*>;
        my $kernelbuild     =  pop @kernelfiles;
        
        my $kernel_version;
        open FH,"tar -tzf $kernelbuild|" or die "Can't look into kernelbuild:$!";
 TARFILES:
        while (my $line = <FH>){
                if ($line =~ m/vmlinuz-(.+)$/) {
                        $kernel_version = $1;
                        last TARFILES ;
                }
        }
        my $id = qx($execpath/artemis-testrun new --macroprecond=/data/bancroft/artemis/live/repository/macropreconditions/kernel/kernel_boot.mpc --hostname=$host -Dkernel_version=$kernel_version -Dkernelpkg=$kernelbuild --owner=mhentsc3 --topic=Kernel);
        print "Kernel testrun on $host: $id";
}



# randomly define the one host that runs a kernel test
my $random = int(rand((scalar keys %hostliste) - 1));
my $count  = 0;

HOST:
foreach my $host (keys %hostliste) {
        next HOST if not $hostliste{$host};
        if ($count == $random) {
                gen_kernel($host);
        } else {
                gen_xen($host);
        }
        $count++;
}
